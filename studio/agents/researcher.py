"""Agent 2: Researcher. Builds a sourced dossier on the topic (Mode B) or chosen opportunity (Mode A)."""
from __future__ import annotations

from .. import tools
from ..llm import LLMRouter
from ..state import RunState

SYSTEM = """You are the Researcher on an AI film studio team. You receive a topic and raw source excerpts.
Write a research dossier a screenwriter can use. Rules:
- Use ONLY facts present in the excerpts, or label them clearly as "unverified".
- Cite sources as [S1], [S2] matching the numbered excerpts.
- Find the surprising, little-known angles. Skip the obvious summary.
- If the topic is fiction or speculative, say so and instead collect real-world facts that can ground it."""

USER = """TOPIC: {topic}

SOURCE EXCERPTS:
{sources}

Write the dossier in markdown with these sections:
## Core facts (cited)
## Surprising angles
## Key people, places, objects
## What has already been done to death (avoid)
## Open questions / unverified"""


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    topic = state.topic or ""
    if state.chosen_opportunity:
        topic = f"{state.chosen_opportunity['title']}: {state.chosen_opportunity['premise']}"
        state.topic = topic
    state.note(f"Researcher: gathering sources for '{topic[:60]}'")
    hits = tools.wikipedia_search(topic.split(":")[0], n=4)
    excerpts = []
    for h in hits:
        ex = tools.wikipedia_extract(h["title"])
        if ex:
            excerpts.append(ex)
    sources = "\n\n".join(f"[S{i + 1}] {e['title']} ({e['url']})\n{e['text']}" for i, e in enumerate(excerpts))
    if not sources:
        sources = "(no web sources reachable; rely on your own knowledge and mark every claim 'unverified')"
    state.dossier = llm.complete(SYSTEM, USER.format(topic=topic, sources=sources), tier="fast")
    if excerpts:
        state.dossier += "\n\n## Sources\n" + "\n".join(f"- [S{i + 1}] {e['title']}: {e['url']}" for i, e in enumerate(excerpts))
    state.status = "researched"
    state.note(f"Researcher: dossier written ({len(state.dossier.split())} words, {len(excerpts)} sources)")
    return state
