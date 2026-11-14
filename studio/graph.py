"""Orchestrator. Plain Python state machine: easy to read, resume and later move to LangGraph or Temporal."""
from __future__ import annotations

import copy

from .agents import critic, ideation, researcher, scriptwriter, story_architect, trend_scout
from .export import export
from .llm import BudgetExceeded, LLMRouter
from .state import RunState

# Stage order after the idea is chosen. Each stage skips itself if its output already exists (resume support).
PIPELINE = ["research", "ideation", "story", "script_loop", "export"]


def choose_opportunity(state: RunState, pick: int | None, auto: bool) -> RunState:
    print("\nTop film opportunities:\n")
    for i, o in enumerate(state.opportunities, 1):
        print(f" {i}. [{o.get('genre')}] {o.get('title')}  (novelty {o.get('novelty_score')})\n    {o.get('premise')}\n")
    if auto or pick is None:
        idx = 0
        if not auto:
            raw = input("Pick a number (Enter = 1): ").strip()
            idx = int(raw) - 1 if raw.isdigit() else 0
    else:
        idx = pick - 1
    state.chosen_opportunity = state.opportunities[max(0, min(idx, len(state.opportunities) - 1))]
    state.note(f"Chosen: {state.chosen_opportunity['title']}")
    return state


def script_loop(state: RunState, llm: LLMRouter, cfg: dict) -> RunState:
    max_rounds = cfg["quality"]["max_script_rounds"]
    while True:
        state = scriptwriter.run(state, llm, cfg)
        state = critic.run(state, llm, cfg)
        if not state.script_passed and not state.current_is_best:
            # A rewrite made things worse. Go back to the best draft and rewrite from there.
            state.note(f"Round {state.script_rounds} scored worse than the best draft; reverting to the best draft")
            state.scenes = copy.deepcopy(state.best_scenes)
            state.critic_notes = copy.deepcopy(state.best_notes)
            state.script_scores = dict(state.best_scores)
            state.script_score = state.best_scores.get("average", 0.0)
        state.tokens_used = llm.used
        state.save()
        if state.script_passed:
            break
        if state.script_rounds >= max_rounds:
            state.warn(f"Script did not pass the quality gate after {max_rounds} rounds. The best draft is kept; read the open critic notes.")
            break
    return state


def run_pipeline(state: RunState, llm: LLMRouter, cfg: dict, pick: int | None = None, auto: bool = False) -> RunState:
    try:
        if state.mode == "discover" and not state.chosen_opportunity:
            if not state.opportunities:
                state = trend_scout.run(state, llm, cfg)
                state.save()
            state = choose_opportunity(state, pick, auto)
            state.save()

        if not state.dossier:
            state = researcher.run(state, llm, cfg)
            state.save()
        if not state.concept:
            state = ideation.run(state, llm, cfg)
            state.save()
        if not state.beat_sheet:
            state = story_architect.run(state, llm, cfg)
            state.save()
        if not state.script_passed and state.script_rounds < cfg["quality"]["max_script_rounds"]:
            state = script_loop(state, llm, cfg)
        state.status = "script_ready" if state.script_passed else "script_needs_review"
    except BudgetExceeded as e:
        state.status = "stopped_budget"
        state.note(f"STOPPED: {e}")
        state.tokens_used = llm.used
        state.save()
        raise
    state.tokens_used = llm.used
    state.save()
    if state.concept and state.scenes:
        export(state)
    return state
