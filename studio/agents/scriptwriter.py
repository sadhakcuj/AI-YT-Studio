"""Agent 6: Scriptwriter. Writes scene by scene so a small local model stays coherent."""
from __future__ import annotations

from ..llm import LLMRouter
from ..rules import REAL_WORLD_RULES
from ..script_checks import cast_names, normalize_scene
from ..state import RunState

SYSTEM = """You are the Scriptwriter on an AI film studio team, an award-winning screenwriter.
You write ONE scene at a time as spoken lines for a narrator and characters. Rules:
- Natural, specific dialogue. People interrupt, hesitate, hide things. No exposition dumps. No cliches.
- Narration is vivid and economical. Never repeat what the picture will already show.
- Every line has a speaker: exactly "NARRATOR" or a name from the cast, spelled as in the cast list.
- Characters speak in short exchanges, under 45 words a line. Never write a character's inner thoughts as a long speech: give them to NARRATOR or cut them.
- Narrator lines are under 100 words each.
- If the scene form is "narration", every line is NARRATOR. If it is "dialogue" or "mixed", at least 2 lines are spoken by characters.
- Add a short "visual" note per line (what the viewer sees) so the Visual Director can use it later.
- Match the target length: about {words} words of spoken text in this scene.
- Keep facts consistent with the dossier. Keep voice and tone consistent with earlier scenes.

""" + REAL_WORLD_RULES

USER = """CONCEPT: {concept}
CAST: {cast}
THEME: {theme}

DOSSIER FACTS:
{dossier}

STORY SO FAR (summary of previous scenes):
{so_far}

SCENE TO WRITE (form: {form}):
{scene}

{notes}
Return JSON: {{"scene_id": str, "lines": [{{"speaker": str, "text": str, "visual": str, "emotion": str}}]}}"""


def _targets(state: RunState, scene_ids: list[str], first_draft: bool) -> tuple[set[str], dict[str, list[str]], list[str]]:
    """Decide which scenes to (re)write and which notes each gets."""
    if first_draft:
        return set(scene_ids), {}, []
    specific: dict[str, list[str]] = {}
    general: list[str] = []
    rewrite_all = False
    for n in state.critic_notes:
        sid = n.get("scene_id")
        if n.get("global"):
            rewrite_all = True
        if sid in scene_ids:
            specific.setdefault(sid, []).append(n.get("note", ""))
        else:
            general.append(n.get("note", ""))
    targets = set(scene_ids) if rewrite_all or not specific else set(specific)
    return targets, specific, general


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    """First draft when state.scenes is empty. Later rounds rewrite only the scenes the critic flagged."""
    wpm = cfg["film"]["words_per_minute"]
    scene_specs = [s for a in state.beat_sheet["acts"] for s in a["scenes"]]
    scene_ids = [s["scene_id"] for s in scene_specs]
    names = cast_names(state)
    cast = ", ".join(f"{c['name']} ({c.get('role', '')}, voice: {c.get('voice', '')})" for c in state.concept.get("characters", []) if c.get("name")) or "NARRATOR only"

    existing = {s["scene_id"]: s for s in state.scenes}
    first_draft = not existing
    targets, specific, general = _targets(state, scene_ids, first_draft)

    out: list[dict] = []
    so_far: list[str] = []
    for spec in scene_specs:
        sid = spec["scene_id"]
        summary = f"{sid} {spec.get('title', '')}: {spec.get('turn', '')}"
        if sid not in targets and sid in existing:
            out.append(existing[sid])
            so_far.append(summary)
            continue
        state.note(f"Scriptwriter: {'writing' if first_draft else 'rewriting'} scene {sid}")
        words = max(60, int(spec.get("target_seconds", 45) / 60 * wpm))
        notes = specific.get(sid, []) + general
        note_text = ""
        if notes:
            note_text = (
                "CRITIC NOTES TO FIX (the rewrite must visibly fix these, not just reword):\n"
                + "\n".join(f"- {x}" for x in notes)
                + "\nPREVIOUS VERSION:\n"
                + str(existing.get(sid, {}).get("lines", ""))[:2500]
                + "\n"
            )
        raw = llm.complete_json(
            SYSTEM.format(words=words),
            USER.format(
                concept=f"{state.concept['title']}: {state.concept['logline']}",
                cast=cast,
                theme=state.beat_sheet.get("theme", ""),
                dossier=state.dossier[:2500],
                so_far="\n".join(so_far) or "(this is the opening)",
                form=spec.get("form", "mixed"),
                scene=spec,
                notes=note_text,
            ),
            tier="smart",
            max_tokens=3000,
        )
        scene = normalize_scene(raw, names)
        scene["scene_id"] = sid
        scene["title"] = spec.get("title", "")
        scene["setting"] = spec.get("setting", "")
        out.append(scene)
        so_far.append(summary)
    state.scenes = out
    state.status = "script_drafted"
    return state
