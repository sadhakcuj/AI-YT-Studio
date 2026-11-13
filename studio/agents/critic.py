"""Agent 7: Script Critic. Scores the script on a rubric and returns scene-specific fix notes."""
from __future__ import annotations

from ..llm import LLMRouter
from ..state import RunState

CRITERIA = ["originality", "hook", "story", "dialogue", "pacing", "emotion"]

SYSTEM = """You are the Script Critic on an AI film studio team, a ruthless but fair script editor.
Score the script 1-10 on: originality, hook, story, dialogue, pacing, emotion. Be harsh: 8 means excellent,
5 means average, never inflate. Find cliches, plot holes, flat dialogue, exposition dumps, repeated beats.
For every problem give a note tied to a scene_id (or "ALL" if global) with a concrete fix instruction."""

USER = """CONCEPT: {concept}
THEME: {theme}

SCRIPT:
{script}

Return JSON: {{"scores": {{"originality": n, "hook": n, "story": n, "dialogue": n, "pacing": n, "emotion": n}},
"notes": [{{"scene_id": str, "note": str}}]}}"""


def script_text(state: RunState) -> str:
    parts = []
    for s in state.scenes:
        parts.append(f"### {s['scene_id']} {s.get('title', '')}")
        for ln in s.get("lines", []):
            parts.append(f"{ln.get('speaker', '?')}: {ln.get('text', '')}")
    return "\n".join(parts)


def word_count(state: RunState) -> int:
    return sum(len(str(ln.get("text", "")).split()) for s in state.scenes for ln in s.get("lines", []))


def run(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    q = cfg["quality"]
    state.script_rounds += 1
    state.note(f"Script Critic: scoring round {state.script_rounds}")
    text = script_text(state)
    verdict = llm.complete_json(
        SYSTEM,
        USER.format(concept=state.concept["title"], theme=state.beat_sheet.get("theme", ""), script=text[:14000]),
        tier="smart",
        max_tokens=2500,
    )
    scores = {k: float(verdict.get("scores", {}).get(k, 0)) for k in CRITERIA}
    avg = sum(scores.values()) / len(scores)

    # Hard checks the model cannot talk its way past
    words = word_count(state)
    f = cfg["film"]
    est_minutes = words / f["words_per_minute"]
    notes = list(verdict.get("notes", []))
    length_ok = f["min_minutes"] <= est_minutes <= f["max_minutes"]
    if not length_ok:
        direction = "Expand scenes with richer beats" if est_minutes < f["min_minutes"] else "Tighten scenes and cut filler"
        notes.append({"scene_id": "ALL", "note": f"Runtime is about {est_minutes:.1f} minutes, target {f['min_minutes']}-{f['max_minutes']}. {direction}."})

    state.script_scores = {**scores, "average": round(avg, 2), "est_minutes": round(est_minutes, 1), "words": words}
    state.script_score = avg
    state.critic_notes = notes
    state.script_passed = avg >= q["script_pass_score"] and min(scores.values()) >= q["script_min_single_score"] and length_ok
    state.note(f"Script Critic: avg {avg:.1f}, ~{est_minutes:.1f} min, {'PASS' if state.script_passed else 'revise'}")
    return state
