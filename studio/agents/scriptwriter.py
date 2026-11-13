"""Agent 6: Scriptwriter. Writes scene by scene so a small local model stays coherent."""
from __future__ import annotations

from ..llm import LLMRouter
from ..state import RunState

SYSTEM = """You are the Scriptwriter on an AI film studio team, an award-winning screenwriter.
You write ONE scene at a time as spoken lines for narrator and characters. Rules:
- Natural, specific dialogue. People interrupt, hesitate, hide things. No exposition dumps. No cliches.
- Narration is vivid and economical. Never repeat what the picture will already show.
- Every line has a speaker: "NARRATOR" or a character name from the cast.
- Add a short "visual" note per line (what the viewer sees) so the Visual Director can use it later.
- Match the target length: about {words} words of spoken text in this scene.
- Keep facts consistent with the dossier. Keep voice and tone consistent with earlier scenes."""

USER = """CONCEPT: {concept}
CAST: {cast}
THEME: {theme}

STORY SO FAR (summary of previous scenes):
{so_far}

SCENE TO WRITE:
{scene}

{notes}
Return JSON: {{"scene_id": str, "lines": [{{"speaker": str, "text": str, "visual": str, "emotion": str}}]}}"""


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    """First draft when state.scenes is empty. On later rounds only scenes named in critic notes are rewritten."""
    wpm = cfg["film"]["words_per_minute"]
    scene_specs = [s for a in state.beat_sheet["acts"] for s in a["scenes"]]
    cast = ", ".join(f"{c['name']} ({c.get('role', '')}, voice: {c.get('voice', '')})" for c in state.concept.get("characters", [])) or "NARRATOR only"
    notes_by_scene: dict[str, list[str]] = {}
    for n in state.critic_notes:
        notes_by_scene.setdefault(n.get("scene_id", "ALL"), []).append(n.get("note", ""))

    existing = {s["scene_id"]: s for s in state.scenes}
    first_draft = not existing
    out: list[dict] = []
    so_far: list[str] = []
    for spec in scene_specs:
        sid = spec["scene_id"]
        notes = notes_by_scene.get(sid, []) + notes_by_scene.get("ALL", [])
        if not first_draft and sid in existing and not notes:
            out.append(existing[sid])
            so_far.append(f"{sid} {spec['title']}: {spec['turn']}")
            continue
        state.note(f"Scriptwriter: {'writing' if first_draft else 'rewriting'} scene {sid}")
        words = max(60, int(spec.get("target_seconds", 45) / 60 * wpm))
        note_text = ""
        if notes:
            note_text = "CRITIC NOTES TO FIX:\n" + "\n".join(f"- {x}" for x in notes) + "\nPREVIOUS VERSION:\n" + str(existing.get(sid, {}).get("lines", ""))[:2500] + "\n"
        scene = llm.complete_json(
            SYSTEM.format(words=words),
            USER.format(
                concept=f"{state.concept['title']}: {state.concept['logline']}",
                cast=cast,
                theme=state.beat_sheet.get("theme", ""),
                so_far="\n".join(so_far) or "(this is the opening)",
                scene=spec,
                notes=note_text,
            ),
            tier="smart",
            max_tokens=3000,
        )
        scene["scene_id"] = sid
        scene["title"] = spec.get("title", "")
        scene["setting"] = spec.get("setting", "")
        out.append(scene)
        so_far.append(f"{sid} {spec['title']}: {spec['turn']}")
    state.scenes = out
    state.status = "script_drafted"
    return state
