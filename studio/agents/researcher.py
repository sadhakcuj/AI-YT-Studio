"""Agent 2: Researcher. Plans searches, filters sources, writes a dossier, then fact-checks it."""
from __future__ import annotations

from .. import tools
from ..llm import LLMRouter
from ..rules import REAL_WORLD_RULES
from ..state import RunState

PLANNER_SYSTEM = """You are the Research Planner on an AI film studio team.
Given a film topic, write up to 3 short Wikipedia search queries that name the core subject, most specific first.
Also say whether the topic involves real people, religions, beliefs, or living organisations.
Return JSON: {"queries": [str], "involves_real_people_or_beliefs": bool, "reason": str}"""

FILTER_SYSTEM = """You are the Source Filter on an AI film studio team.
Keep only the pages that are directly about the topic. Drop pages about related but different subjects
(other people, other organisations, other movements). Return JSON: {"keep": [exact page titles]}, at most 4."""

SYSTEM = """You are the Researcher on an AI film studio team. You receive a topic and raw source excerpts.
Write a research dossier a screenwriter can use. Rules:
- Use ONLY facts stated in the excerpts. Anything else must be labelled "unverified".
- Cite sources as [S1], [S2] matching the numbered excerpts.
- Do not speculate. Do not give causes, motives or links between subjects unless an excerpt states them.
- Two subjects mentioned in different excerpts are separate unless an excerpt connects them.
- Never allege crimes or wrongdoing against any person or organisation unless an excerpt states it, and then use its exact wording.
- "Surprising angles" may only restate sourced facts in a more striking way. It must not add claims.
- If the topic is fiction or speculative, say so and collect real-world facts that can ground it."""

USER = """TOPIC: {topic}

SOURCE EXCERPTS:
{sources}

Write the dossier in markdown with these sections:
## Core facts (cited)
## Surprising angles
## Key people, places, objects
## What has already been done to death (avoid)
## Open questions / unverified"""

FACT_SYSTEM = """You are the Fact Checker on an AI film studio team.
Check each bullet or sentence of the dossier against the excerpts. List every claim that is not directly stated
in the excerpts, that connects two subjects the excerpts do not connect, or that alleges wrongdoing the excerpts
do not state. Return JSON: {"unsupported": [exact text of each such claim]}"""


def _plan(topic: str, llm: LLMRouter) -> dict:
    core = topic.split(":")[0].strip()
    try:
        plan = llm.complete_json(PLANNER_SYSTEM, f"TOPIC: {topic}", tier="fast")
        if not isinstance(plan, dict):
            raise ValueError("plan is not an object")
    except ValueError:
        plan = {}
    queries = [q.strip() for q in plan.get("queries", []) if isinstance(q, str) and q.strip()][:3]
    plan["queries"] = queries or [core]
    return plan


def _pick_sources(topic: str, queries: list[str], llm: LLMRouter) -> list[dict]:
    by_query: list[list[str]] = []
    seen: set[str] = set()
    for q in queries:
        titles = []
        for h in tools.wikipedia_search(q, n=3):
            if h["title"] not in seen:
                seen.add(h["title"])
                titles.append(h["title"])
        by_query.append(titles)
    candidates = [t for ts in by_query for t in ts]
    if not candidates:
        return []
    keep: list[str] = []
    try:
        verdict = llm.complete_json(FILTER_SYSTEM, f"TOPIC: {topic}\n\nPAGES:\n" + "\n".join(f"- {t}" for t in candidates), tier="fast")
        raw = verdict.get("keep", []) if isinstance(verdict, dict) else verdict
        keep = [t for t in raw if t in candidates][:4]
    except ValueError:
        keep = []
    if not keep:  # fall back to the top hit of each query
        keep = [ts[0] for ts in by_query if ts][:4]
    excerpts = []
    for t in keep:
        ex = tools.wikipedia_extract(t, max_chars=3000)
        if ex:
            excerpts.append(ex)
    return excerpts


def _strip_unsupported(dossier: str, unsupported: list[str]) -> tuple[str, int]:
    kept, removed = [], 0
    claims = [u.strip() for u in unsupported if len(u.strip()) >= 15]
    for line in dossier.split("\n"):
        plain = line.strip(" -*")
        if any(u in line or (len(plain) >= 15 and plain in u) for u in claims):
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    topic = state.topic or ""
    if state.chosen_opportunity:
        topic = f"{state.chosen_opportunity['title']}: {state.chosen_opportunity['premise']}"
        state.topic = topic
    state.note(f"Researcher: planning searches for '{topic[:60]}'")
    plan = _plan(topic, llm)
    state.sensitive = bool(plan.get("involves_real_people_or_beliefs"))
    if state.sensitive:
        state.warn("Topic involves real people, beliefs or organisations. Fact-check the script by hand before any use.")

    excerpts = _pick_sources(topic, plan["queries"], llm)
    state.note(f"Researcher: {len(excerpts)} sources kept: {[e['title'] for e in excerpts]}")
    sources = "\n\n".join(f"[S{i + 1}] {e['title']} ({e['url']})\n{e['text']}" for i, e in enumerate(excerpts))
    if not excerpts:
        state.warn("No web sources found. The dossier comes from model memory and is unverified.")
        sources = "(no web sources reachable; rely on your own knowledge and mark every claim 'unverified')"

    dossier = llm.complete(SYSTEM + "\n\n" + REAL_WORLD_RULES, USER.format(topic=topic, sources=sources), tier="fast")

    if excerpts:
        try:
            verdict = llm.complete_json(FACT_SYSTEM, f"EXCERPTS:\n{sources}\n\nDOSSIER:\n{dossier}", tier="fast")
            unsupported = verdict.get("unsupported", []) if isinstance(verdict, dict) else []
            unsupported = [u for u in unsupported if isinstance(u, str)]
        except ValueError:
            unsupported = []
            state.warn("Fact check of the dossier failed. Check its claims against the sources by hand.")
        dossier, removed = _strip_unsupported(dossier, unsupported)
        if removed:
            state.note(f"Fact Checker: removed {removed} unsupported dossier lines")
        dossier += "\n\n## Sources\n" + "\n".join(f"- [S{i + 1}] {e['title']}: {e['url']}" for i, e in enumerate(excerpts))

    state.dossier = dossier
    state.status = "researched"
    state.note(f"Researcher: dossier written ({len(dossier.split())} words)")
    return state
