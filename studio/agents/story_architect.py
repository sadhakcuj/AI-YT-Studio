"""Agent 5: Story Architect. Builds the beat sheet with retention peaks."""
from __future__ import annotations

from ..llm import LLMRouter
from ..rules import REAL_WORLD_RULES
from ..state import RunState

SYSTEM = """You are the Story Architect on an AI film studio team, a veteran story editor for online video.
Build a beat sheet for the chosen concept. Rules:
- The first 30 seconds must be a gripping hook, not setup.
- A new reveal, turn or escalation at least every 60-90 seconds (retention peaks).
- Exactly {acts} acts, {scenes} scenes per act. Each scene has one clear purpose and one change.
- scene_id is act.scene, for example 1.1, 1.2, 2.1.
- Every scene must move the plot. No scene may repeat the previous scene's beat.
- At least half the scenes have form "dialogue" or "mixed". Use form "narration" for at most 4 scenes.
- In "characters" use only names from the concept's cast.
- The ending must be earned and land an emotion or idea people want to share.
- Target runtime {minutes} minutes in total.

""" + REAL_WORLD_RULES

USER = """CONCEPT:
{concept}

DOSSIER (facts to use):
{dossier}

Return JSON: {{"theme": str, "opening_hook": str, "ending": str,
"acts": [{{"act": int, "purpose": str, "scenes": [{{"scene_id": str, "title": str, "setting": str,
"purpose": str, "characters": [str], "turn": str, "target_seconds": int, "form": "narration" | "dialogue" | "mixed"}}]}}]}}"""


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    f = cfg["film"]
    state.note("Story Architect: building beat sheet")
    system = SYSTEM.format(acts=f["acts"], scenes=f["scenes_per_act"], minutes=f["target_minutes"])
    state.beat_sheet = llm.complete_json(
        system,
        USER.format(concept=state.concept, dossier=state.dossier[:5000]),
        tier="smart",
        max_tokens=6000,
    )
    n = sum(len(a.get("scenes", [])) for a in state.beat_sheet.get("acts", []))
    state.status = "beat_sheet_ready"
    state.note(f"Story Architect: {n} scenes planned")
    return state
