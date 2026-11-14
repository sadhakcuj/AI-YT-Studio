"""LLM adapters. Agents only call LLMRouter.complete / complete_json; swap providers in settings.yaml."""
from __future__ import annotations

import json
import os
import re
from typing import Literal, Protocol

import httpx

Tier = Literal["fast", "smart"]


class BudgetExceeded(RuntimeError):
    pass


class Backend(Protocol):
    def complete(self, system: str, user: str, model: str, max_tokens: int) -> tuple[str, int]:
        """Return (text, tokens_used)."""


class OllamaBackend:
    def __init__(self, host: str, timeout: float, num_ctx: int = 8192):
        self.host, self.timeout, self.num_ctx = host.rstrip("/"), timeout, num_ctx

    def complete(self, system: str, user: str, model: str, max_tokens: int) -> tuple[str, int]:
        r = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"num_predict": max_tokens, "temperature": 0.8, "num_ctx": self.num_ctx},
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        used = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        return data["message"]["content"], used


class AnthropicBackend:
    def __init__(self, timeout: float):
        import anthropic

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY missing. Put it in .env or switch provider to ollama.")
        self.client = anthropic.Anthropic(timeout=timeout)

    def complete(self, system: str, user: str, model: str, max_tokens: int) -> tuple[str, int]:
        msg = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text, msg.usage.input_tokens + msg.usage.output_tokens


def extract_json(text: str):
    """Pull the first JSON object or array out of model output, tolerating code fences and chatter."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON in model output: {text[:200]!r}")


class LLMRouter:
    """Routes each call to the backend and model for its tier, and enforces the token budget."""

    def __init__(self, settings: dict, backends: dict[Tier, tuple[Backend, str]] | None = None):
        cfg = settings["llm"]
        self.max_tokens = cfg["max_tokens"]
        self.budget = settings["budget"]["max_llm_tokens_per_run"]
        self.used = 0
        if backends:
            self.backends = backends
            return
        built: dict[str, Backend] = {}

        def backend_for(provider: str) -> Backend:
            if provider not in built:
                if provider == "ollama":
                    built[provider] = OllamaBackend(cfg["ollama"]["host"], cfg["timeout_seconds"], cfg["ollama"].get("num_ctx", 8192))
                elif provider == "anthropic":
                    built[provider] = AnthropicBackend(cfg["timeout_seconds"])
                else:
                    raise ValueError(f"Unknown provider {provider!r}")
            return built[provider]

        self.backends = {}
        for tier in ("fast", "smart"):
            provider = cfg[f"provider_{tier}"]
            self.backends[tier] = (backend_for(provider), cfg[provider][f"{tier}_model"])

    def complete(self, system: str, user: str, tier: Tier = "smart", max_tokens: int | None = None) -> str:
        if self.used >= self.budget:
            raise BudgetExceeded(f"Token budget {self.budget} reached. Raise budget.max_llm_tokens_per_run to continue.")
        backend, model = self.backends[tier]
        text, used = backend.complete(system, user, model, max_tokens or self.max_tokens)
        self.used += used
        return text

    def complete_json(self, system: str, user: str, tier: Tier = "smart", retries: int = 2, max_tokens: int | None = None):
        sys_json = system + "\n\nReturn ONLY valid JSON. No commentary, no markdown fences."
        last: Exception | None = None
        prompt = user
        for _ in range(retries + 1):
            raw = self.complete(sys_json, prompt, tier, max_tokens)
            try:
                return extract_json(raw)
            except ValueError as e:
                last = e
                prompt = user + "\n\nYour previous reply was not valid JSON. Reply with valid JSON only."
        raise ValueError(f"Model failed to return JSON after {retries + 1} tries: {last}")
