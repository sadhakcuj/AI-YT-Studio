"""Agents 3 and 4: Ideation Expert and Originality Checker."""
from __future__ import annotations

from .. import history, tools
from ..llm import LLMRouter
from ..rules import REAL_WORLD_RULES
from ..state import RunState

IDEATE_SYSTEM = """You are the Ideation Expert on an AI film studio team, a world-class creative strategist.
Turn the research dossier into 5 DISTINCT film concepts for a 10-15 minute narrated film with character dialogue,
for a global English YouTube audience. Rules:
- Each concept must be something viewers have never seen. No generic or saturated ideas.
- The title must be a compelling film title, not just the name of a place, person or topic.
- Each must have a magnetic hook that works in the first 30 seconds.
- Each must have 2-4 named speaking characters plus the narrator.
- Vary the form: do not give five versions of the same idea.
- Ground in the dossier facts where it is non-fiction.
- List in real_people_named every real person or living organisation the film would name.

""" + REAL_WORLD_RULES

IDEATE_USER = """DOSSIER:
{dossier}

TOPIC: {topic}
RECENT GENRES (avoid repeating): {recent}
{feedback}
Return JSON: {{"concepts": [{{"title": str, "genre": str, "logline": str, "hook": str,
"central_twist": str, "tone": str, "characters": [{{"name": str, "role": str, "voice": str}}],
"real_people_named": [str], "why_unique": str, "originality_score": number 1-10}}]}}"""

JUDGE_SYSTEM = """You are the Originality Checker. Compare a film concept with existing videos found by search.
Fail the concept if it is a near-duplicate of an existing video or a well-known film, book or franchise.
Return JSON: {"pass": bool, "reason": str, "closest_match": str}"""


def valid_concept(c: dict) -> bool:
    chars = [x for x in c.get("characters", []) if isinstance(x, dict) and x.get("name")]
    return bool(c.get("title") and c.get("logline") and len(chars) >= 2)


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
        concepts = [c for c in concepts if isinstance(c, dict)]
        usable = [c for c in concepts if valid_concept(c)]
        if len(usable) < len(concepts):
            state.note(f"Ideation: dropped {len(concepts) - len(usable)} concepts with no title, logline or 2 named characters")
        usable = sorted(usable, key=lambda c: c.get("originality_score", 0), reverse=True)

        survivors = []
        for c in usable:
            if check_originality(c, llm, state):
                survivors.append(c)
            else:
                state.note(f"Originality Checker: rejected '{c.get('title')}'")
        state.concepts = survivors
        if survivors:
            return _choose(state, survivors[0])
        state.concept_regenerations += 1
        if state.concept_regenerations > cfg["quality"]["max_concept_regenerations"]:
            fallback = (usable or concepts or [None])[0]
            if fallback is None:
                raise ValueError("Ideation produced no usable concept. Try a clearer topic or a stronger model.")
            state.warn("All concepts failed the originality or quality check. The best raw concept was used.")
            return _choose(state, fallback)
        feedback = "\nPREVIOUS CONCEPTS WERE TOO SIMILAR TO EXISTING WORK OR INCOMPLETE. Be far more daring, and give every concept 2-4 named characters.\n"


def _choose(state: RunState, concept: dict) -> RunState:
    state.concept = concept
    history.record_genre(concept.get("genre", "unknown"))
    named = [n for n in concept.get("real_people_named", []) if isinstance(n, str) and n.strip()]
    if named:
        state.warn(f"The film names real people or organisations: {', '.join(named)}. Fact-check every line about them before any use.")
    state.status = "concept_chosen"
    state.note(f"Ideation: chose '{concept['title']}'")
    return state


def check_originality(concept: dict, llm: LLMRouter, state: RunState) -> bool:
    """Compares against YouTube search results only. Without a key there is nothing to compare, so it cannot reject."""
    query = f"{concept.get('title', '')} {concept.get('logline', '')}"[:120]
    matches = tools.youtube_search(query)
    if not matches:
        state.warn("Originality was not checked against YouTube (no YOUTUBE_API_KEY, or no results). Search for similar videos yourself.")
        return True
    listing = "\n".join(f"- {m['title']}" for m in matches)
    try:
        verdict = llm.complete_json(
            JUDGE_SYSTEM,
            f"CONCEPT: {concept.get('title')}: {concept.get('logline')}\n\nEXISTING RESULTS:\n{listing}",
            tier="fast",
        )
        return bool(verdict.get("pass", True)) if isinstance(verdict, dict) else True
    except ValueError:
        return True
