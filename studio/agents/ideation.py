"""Agents 3 and 4: Ideation Expert and Originality Checker."""
from __future__ import annotations

from .. import history, tools
from ..llm import LLMRouter
from ..state import RunState

IDEATE_SYSTEM = """You are the Ideation Expert on an AI film studio team, a world-class creative strategist.
Turn the research dossier into 5 DISTINCT film concepts for a 10-15 minute narrated film with character dialogue,
for a global English YouTube audience. Rules:
- Each concept must be something viewers have never seen. No generic or saturated ideas.
- Each must have a magnetic hook that works in the first 30 seconds.
- Each must have 2-4 memorable characters (a narrator plus speaking characters).
- Vary the form: do not give five versions of the same idea.
- Ground in the dossier facts where it is non-fiction."""

IDEATE_USER = """DOSSIER:
{dossier}

TOPIC: {topic}
RECENT GENRES (avoid repeating): {recent}
{feedback}
Return JSON: {{"concepts": [{{"title": str, "genre": str, "logline": str, "hook": str,
"central_twist": str, "tone": str, "characters": [{{"name": str, "role": str, "voice": str}}],
"why_unique": str, "originality_score": number 1-10}}]}}"""

JUDGE_SYSTEM = """You are the Originality Checker. Compare a film concept with existing videos found by search.
Fail the concept if it is a near-duplicate of an existing video or a well-known film, book or franchise.
Return JSON: {"pass": bool, "reason": str, "closest_match": str}"""


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    recent = history.recent_genres(cfg["discovery"]["recent_genres_to_avoid"])
    feedback = ""
    while True:
        state.note("Ideation Expert: generating 5 concepts")
        data = llm.complete_json(
            IDEATE_SYSTEM,
            IDEATE_USER.format(dossier=state.dossier[:6000], topic=state.topic, recent=", ".join(recent) or "none", feedback=feedback),
            tier="smart",
        )
        concepts = data["concepts"] if isinstance(data, dict) else data
        concepts = sorted(concepts, key=lambda c: c.get("originality_score", 0), reverse=True)

        survivors = []
        for c in concepts:
            if check_originality(c, llm):
                survivors.append(c)
            else:
                state.note(f"Originality Checker: rejected '{c.get('title')}'")
        state.concepts = survivors
        if survivors:
            state.concept = survivors[0]
            history.record_genre(state.concept.get("genre", "unknown"))
            state.status = "concept_chosen"
            state.note(f"Ideation: chose '{state.concept['title']}'")
            return state
        state.concept_regenerations += 1
        if state.concept_regenerations > cfg["quality"]["max_concept_regenerations"]:
            # Fail open with the best raw concept rather than stall the run; flag it for the human.
            state.concept = concepts[0]
            state.note("Ideation: all concepts failed originality check; using best raw concept, FLAGGED for human review")
            state.status = "concept_chosen"
            return state
        feedback = "\nPREVIOUS CONCEPTS WERE TOO SIMILAR TO EXISTING WORK. Be far more daring and original.\n"


def check_originality(concept: dict, llm: LLMRouter) -> bool:
    query = f"{concept.get('title', '')} {concept.get('logline', '')}"[:120]
    matches = tools.youtube_search(query) + tools.wikipedia_search(concept.get("title", ""), n=3)
    if not matches:
        return True  # nothing to compare against (no API key or offline): cannot reject
    listing = "\n".join(f"- {m['title']}" for m in matches)
    try:
        verdict = llm.complete_json(
            JUDGE_SYSTEM,
            f"CONCEPT: {concept.get('title')}: {concept.get('logline')}\n\nEXISTING RESULTS:\n{listing}",
            tier="fast",
        )
        return bool(verdict.get("pass", True))
    except ValueError:
        return True
