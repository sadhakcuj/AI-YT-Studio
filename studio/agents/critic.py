"""Agent 7: Script Critic. Scores the script, runs hard checks in code, returns scene-specific fix notes."""
from __future__ import annotations

import copy

from ..llm import LLMRouter
from ..rules import REAL_WORLD_RULES
from ..script_checks import hard_checks
from ..state import RunState

CRITERIA = ["originality", "hook", "story", "dialogue", "pacing", "emotion"]

SYSTEM = """You are the Script Critic on an AI film studio team, a ruthless but fair script editor.
Score the script 1-10 on: originality, hook, story, dialogue, pacing, emotion. Be harsh: 8 means excellent,
5 means average, never inflate. Find cliches, plot holes, flat dialogue, exposition dumps, repeated beats.
For every problem give a note tied to a scene_id (or "ALL" if global) with a concrete fix instruction.
Also check accuracy against the dossier facts. Report in accuracy_issues any line that invents words, beliefs
or actions for a real person, contradicts the dossier, puts something in the wrong time, or connects two real
subjects the dossier does not connect. Use an empty list when there are none.

""" + REAL_WORLD_RULES

USER = """CONCEPT: {concept}
THEME: {theme}

DOSSIER FACTS:
{dossier}

SCRIPT:
{script}

Return JSON: {{"scores": {{"originality": n, "hook": n, "story": n, "dialogue": n, "pacing": n, "emotion": n}},
"notes": [{{"scene_id": str, "note": str}}],
"accuracy_issues": [{{"scene_id": str, "issue": str}}]}}"""


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
    f = cfg["film"]
    state.script_rounds += 1
    state.note(f"Script Critic: scoring round {state.script_rounds}")
    verdict = llm.complete_json(
        SYSTEM,
        USER.format(
            concept=state.concept["title"],
            theme=state.beat_sheet.get("theme", ""),
            dossier=state.dossier[:2500],
            script=script_text(state)[:13000],
        ),
        tier="smart",
        max_tokens=2000,
    )
    scores = {k: float(verdict.get("scores", {}).get(k, 0)) for k in CRITERIA}
    avg = sum(scores.values()) / len(scores)
    notes = [n for n in verdict.get("notes", []) if isinstance(n, dict)]

    # Accuracy issues from the model: any one blocks the pass
    accuracy = [a for a in verdict.get("accuracy_issues", []) if isinstance(a, dict) and a.get("issue")]
    for a in accuracy:
        notes.append({"scene_id": a.get("scene_id", "ALL"), "note": f"ACCURACY: {a['issue']}. Remove or replace with sourced fact or fictional characters.", "hard": True})

    # Hard checks the model cannot talk its way past
    hard_notes, dialogue_share = hard_checks(state, cfg)
    notes.extend(hard_notes)
    words = word_count(state)
    est_minutes = words / f["words_per_minute"]
    length_ok = f["min_minutes"] <= est_minutes <= f["max_minutes"]
    if not length_ok:
        direction = "Expand scenes with richer beats" if est_minutes < f["min_minutes"] else "Tighten scenes and cut filler"
        notes.append({"scene_id": "ALL", "note": f"Runtime is about {est_minutes:.1f} minutes, target {f['min_minutes']}-{f['max_minutes']}. {direction}.", "hard": True, "global": True})

    penalties = int(bool(hard_notes)) + int(bool(accuracy)) + int(not length_ok)
    effective = avg - penalties
    state.script_scores = {
        **scores,
        "average": round(avg, 2),
        "est_minutes": round(est_minutes, 1),
        "words": words,
        "dialogue_share": dialogue_share,
        "accuracy_issues": len(accuracy),
        "hard_check_failures": len(hard_notes),
    }
    state.script_score = avg
    state.critic_notes = notes
    state.script_passed = avg >= q["script_pass_score"] and min(scores.values()) >= q["script_min_single_score"] and penalties == 0

    if effective > state.best_effective:
        state.best_effective = effective
        state.best_scenes = copy.deepcopy(state.scenes)
        state.best_notes = copy.deepcopy(notes)
        state.best_scores = dict(state.script_scores)
        state.current_is_best = True
    else:
        state.current_is_best = False
    state.note(f"Script Critic: avg {avg:.1f}, ~{est_minutes:.1f} min, dialogue {dialogue_share:.0%}, {len(hard_notes)} hard-check failures, {len(accuracy)} accuracy issues, {'PASS' if state.script_passed else 'revise'}")
    return state
