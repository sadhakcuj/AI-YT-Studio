"""Writes human-readable and machine-readable outputs for the run. Phase 2 reads script.json."""
from __future__ import annotations

import json

from .agents.critic import script_text
from .state import RunState


def export(state: RunState) -> None:
    d = state.dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "dossier.md").write_text(state.dossier, encoding="utf-8")
    (d / "script.md").write_text(
        f"# {state.concept['title']}\n\n*{state.concept.get('logline', '')}*\n\n"
        f"Genre: {state.concept.get('genre', '')} | Estimated runtime: {state.script_scores.get('est_minutes', '?')} min | "
        f"Critic score: {state.script_scores.get('average', '?')}\n\n" + script_text(state),
        encoding="utf-8",
    )
    (d / "script.json").write_text(
        json.dumps(
            {"concept": state.concept, "beat_sheet": state.beat_sheet, "scenes": state.scenes, "scores": state.script_scores},
            indent=2,
        ),
        encoding="utf-8",
    )
    report = [
        f"# Run {state.run_id}",
        f"- Mode: {state.mode}",
        f"- Topic: {state.topic}",
        f"- Concept: {state.concept['title']}",
        f"- Script passed quality gate: {state.script_passed}",
        f"- Script rounds: {state.script_rounds}",
        f"- Scores: {state.script_scores}",
        f"- Tokens used: {state.tokens_used}",
        "",
        "## Read before use" if state.warnings else "## Warnings",
        *(f"- {w}" for w in state.warnings),
        *([] if state.warnings else ["- none"]),
        "",
        "## Open critic notes" if state.critic_notes and not state.script_passed else "## Notes",
        *(f"- [{n.get('scene_id')}] {n.get('note')}" for n in (state.critic_notes if not state.script_passed else [])),
        "",
        "## Log",
        *state.log,
    ]
    (d / "report.md").write_text("\n".join(report), encoding="utf-8")
