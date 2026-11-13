"""Agent 1: Trend Scout (Mode A). Gathers live signals, then proposes ranked film opportunities across genres."""
from __future__ import annotations

from .. import history, tools
from ..llm import LLMRouter
from ..state import RunState

SYSTEM = """You are the Trend Scout on an AI film studio team. The channel is an open home for amazing, engaging
stories for a global English audience, with no fixed genre. You get live signals (what people are reading and
watching this week). Propose film opportunities for a 10-15 minute narrated film with character dialogue.
Rules:
- Do NOT copy a headline. Use signals only to sense what people are curious about, then invent a fresh angle.
- Each opportunity must feel like something viewers have not seen before.
- Spread across different genres. Avoid the recently used genres you are given.
- Be specific: a concrete premise, not a vague theme."""

USER = """LIVE SIGNALS:
{signals}

GENRE TAGS TO USE: {genres}
RECENTLY USED GENRES (avoid): {recent}

Return JSON: {{"opportunities": [{{"title": str, "genre": str, "premise": str, "hook": str,
"why_now": str, "evidence": [str], "novelty_score": number 1-10}}]}}
Give exactly 8 opportunities, sorted best first."""


def gather_signals(cfg: dict) -> list[dict]:
    d = cfg["discovery"]
    signals = tools.hn_top(d["hn_stories"]) + tools.reddit_top(d["subreddits"], d["reddit_per_sub"]) + tools.youtube_trending()
    signals.sort(key=lambda s: s.get("score", 0), reverse=True)
    return signals[:60]


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    state.note("Trend Scout: gathering signals")
    state.signals = gather_signals(cfg)
    state.note(f"Trend Scout: {len(state.signals)} signals collected")
    sig_text = "\n".join(f"- [{s['source']}] {s['title']}" for s in state.signals) or "(no live signals reachable; use your own sense of what is currently fascinating)"
    recent = history.recent_genres(cfg["discovery"]["recent_genres_to_avoid"])
    data = llm.complete_json(
        SYSTEM,
        USER.format(signals=sig_text, genres=", ".join(cfg["discovery"]["genre_tags"]), recent=", ".join(recent) or "none"),
        tier="fast",
    )
    opps = data["opportunities"] if isinstance(data, dict) else data
    state.opportunities = sorted(opps, key=lambda o: o.get("novelty_score", 0), reverse=True)
    state.status = "opportunities_ready"
    return state
