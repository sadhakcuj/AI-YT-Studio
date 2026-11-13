"""Offline tests: a scripted fake LLM drives the whole pipeline. No network, no GPU, no cost."""
import json

import pytest

from studio import history, tools
from studio.config import load_settings
from studio.graph import run_pipeline
from studio.llm import BudgetExceeded, LLMRouter, extract_json
from studio.state import RunState


class FakeBackend:
    """Answers by sniffing which agent's system prompt it receives."""

    def __init__(self, critic_scores=(5, 9)):
        self.calls = []
        self.critic_scores = list(critic_scores)
        self.critic_i = 0

    def complete(self, system, user, model, max_tokens):
        self.calls.append(system[:40])
        if "Trend Scout" in system:
            out = {"opportunities": [
                {"title": f"Idea {i}", "genre": "mystery", "premise": "p", "hook": "h", "why_now": "w", "evidence": [], "novelty_score": 10 - i}
                for i in range(8)]}
        elif "Researcher" in system:
            return "## Core facts\n- A fact [S1]", 100
        elif "Ideation Expert" in system:
            out = {"concepts": [{"title": "The Clock", "genre": "sci-fi", "logline": "A clock that counts people.", "hook": "h",
                                 "central_twist": "t", "tone": "eerie", "originality_score": 9,
                                 "characters": [{"name": "Mara", "role": "lead", "voice": "calm"}]}]}
        elif "Story Architect" in system:
            out = {"theme": "time", "opening_hook": "h", "ending": "e", "acts": [
                {"act": a, "purpose": "p", "scenes": [
                    {"scene_id": f"{a}.{s}", "title": "T", "setting": "S", "purpose": "p", "characters": ["Mara"],
                     "turn": "turn", "target_seconds": 45, "form": "mixed"} for s in (1, 2)]} for a in (1, 2)]}
        elif "Scriptwriter" in system:
            words = " ".join(["word"] * 400)
            out = {"scene_id": "x", "lines": [{"speaker": "NARRATOR", "text": words, "visual": "v", "emotion": "e"}]}
        elif "Script Critic" in system:
            s = self.critic_scores[min(self.critic_i, len(self.critic_scores) - 1)]
            self.critic_i += 1
            out = {"scores": {k: s for k in ["originality", "hook", "story", "dialogue", "pacing", "emotion"]},
                   "notes": [{"scene_id": "1.1", "note": "Sharpen the dialogue"}]}
        else:
            raise AssertionError(f"unexpected prompt: {system[:80]}")
        return json.dumps(out), 100


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ["hn_top", "reddit_top", "youtube_trending", "youtube_search", "wikipedia_search"]:
        monkeypatch.setattr(tools, name, lambda *a, **k: [])
    monkeypatch.setattr(tools, "wikipedia_extract", lambda *a, **k: None)


def make(cfg_overrides=None, **fake_kw):
    import pathlib
    cfg = load_settings(pathlib.Path(__file__).parent.parent / "config" / "settings.yaml")
    cfg["film"].update({"min_minutes": 1, "max_minutes": 60})
    for sect, vals in (cfg_overrides or {}).items():
        cfg[sect].update(vals)
    fake = FakeBackend(**fake_kw)
    llm = LLMRouter(cfg, backends={"fast": (fake, "f"), "smart": (fake, "s")})
    return cfg, llm, fake


def test_extract_json_handles_fences_and_chatter():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('here: [1, 2, 3] done') == [1, 2, 3]
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_topic_mode_revises_then_passes():
    cfg, llm, fake = make(critic_scores=(5, 9))
    state = run_pipeline(RunState(mode="topic", topic="clocks"), llm, cfg)
    assert state.script_passed and state.script_rounds == 2
    assert state.status == "script_ready"
    for f in ["script.md", "script.json", "dossier.md", "report.md", "state.json"]:
        assert (state.dir / f).exists(), f
    assert len(state.scenes) == 4
    assert history.recent_genres(5) == ["sci-fi"]


def test_discover_mode_auto_picks_top_idea():
    cfg, llm, fake = make(critic_scores=(9,))
    state = run_pipeline(RunState(mode="discover"), llm, cfg, auto=True)
    assert state.chosen_opportunity["title"] == "Idea 0"
    assert state.script_passed


def test_gives_up_after_max_rounds_and_flags_for_human():
    cfg, llm, fake = make(critic_scores=(4,))
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    assert not state.script_passed
    assert state.script_rounds == cfg["quality"]["max_script_rounds"]
    assert state.status == "script_needs_review"
    assert "Open critic notes" in (state.dir / "report.md").read_text()


def test_low_single_score_blocks_pass_even_with_high_average():
    cfg, llm, fake = make(critic_scores=(9,))
    cfg["quality"]["script_min_single_score"] = 9.5
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    assert not state.script_passed


def test_runtime_check_is_enforced():
    cfg, llm, fake = make(critic_scores=(9,))
    cfg["film"].update({"min_minutes": 10, "max_minutes": 15})  # 4 scenes x 400 words = 1600 words = 10.7 min at 150 wpm
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    assert state.script_scores["est_minutes"] == 10.7
    assert state.script_passed
    # Too short for the window: the hard length check must fail even though the model scored 9
    cfg2, llm2, _ = make(critic_scores=(9,))
    cfg2["film"].update({"min_minutes": 12, "max_minutes": 15})
    short = run_pipeline(RunState(mode="topic", topic="x"), llm2, cfg2)
    assert not short.script_passed
    assert any("Runtime" in n["note"] for n in short.critic_notes)


def test_budget_stops_run_and_state_is_resumable():
    cfg, llm, fake = make(critic_scores=(9,))
    llm.budget = 300  # 3 calls at 100 tokens
    state = RunState(mode="topic", topic="x")
    with pytest.raises(BudgetExceeded):
        run_pipeline(state, llm, cfg)
    assert state.status == "stopped_budget"
    loaded = RunState.load(state.run_id)
    assert loaded.dossier  # work done before the stop is kept
    cfg2, llm2, _ = make(critic_scores=(9,))
    done = run_pipeline(loaded, llm2, cfg2)
    assert done.script_passed
