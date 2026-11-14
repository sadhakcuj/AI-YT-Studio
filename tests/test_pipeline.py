"""Offline tests: a scripted fake LLM drives the whole pipeline. No network, no GPU, no cost."""
import json
import pathlib

import pytest

from studio import history, tools
from studio.config import load_settings
from studio.graph import run_pipeline
from studio.llm import BudgetExceeded, LLMRouter, extract_json
from studio.script_checks import canonical_speaker, hard_checks, normalize_scene
from studio.state import RunState


class FakeBackend:
    """Answers by sniffing which agent's system prompt it receives."""

    def __init__(self, critic_scores=(5, 9), sensitive=False, accuracy_issues=None, dossier="## Core facts\n- A fact [S1]",
                 unsupported=None):
        self.calls = []
        self.critic_scores = list(critic_scores)
        self.critic_i = 0
        self.scene_calls = 0
        self.sensitive = sensitive
        self.accuracy_issues = accuracy_issues or []
        self.dossier = dossier
        self.unsupported = unsupported or []

    def complete(self, system, user, model, max_tokens):
        self.calls.append(system[:30])
        if "Trend Scout" in system:
            out = {"opportunities": [
                {"title": f"Idea {i}", "genre": "mystery", "premise": "p", "hook": "h", "why_now": "w", "evidence": [], "novelty_score": 10 - i}
                for i in range(8)]}
        elif "Research Planner" in system:
            out = {"queries": ["clocks", "history of clocks"], "involves_real_people_or_beliefs": self.sensitive, "reason": "r"}
        elif "Source Filter" in system:
            out = {"keep": ["Clock"]}
        elif "Fact Checker" in system:
            out = {"unsupported": self.unsupported}
        elif "Researcher" in system:
            return self.dossier, 100
        elif "Ideation Expert" in system:
            out = {"concepts": [
                {"title": "No Cast", "genre": "sci-fi", "logline": "x", "originality_score": 10, "characters": []},
                {"title": "The Clock", "genre": "sci-fi", "logline": "A clock that counts people.", "hook": "h",
                 "central_twist": "t", "tone": "eerie", "originality_score": 9, "real_people_named": [],
                 "characters": [{"name": "Mara", "role": "lead", "voice": "calm"}, {"name": "Jon", "role": "friend", "voice": "dry"}]}]}
        elif "Story Architect" in system:
            out = {"theme": "time", "opening_hook": "h", "ending": "e", "acts": [
                {"act": a, "purpose": "p", "scenes": [
                    {"scene_id": f"{a}.{s}", "title": "T", "setting": "S", "purpose": "p", "characters": ["Mara"],
                     "turn": "turn", "target_seconds": 45, "form": "mixed"} for s in (1, 2)]} for a in (1, 2)]}
        elif "Scriptwriter" in system:
            self.scene_calls += 1
            narr = " ".join(["word"] * 75)
            talk = " ".join(["word"] * 50)
            tag = f"v{self.scene_calls}"
            out = {"scene_id": "x", "lines": (
                [{"speaker": "narrator", "text": narr, "visual": tag, "emotion": "e"} for _ in range(4)]
                + [{"speaker": "MARA", "text": talk, "visual": tag, "emotion": "e"} for _ in range(2)])}
        elif "Script Critic" in system:
            s = self.critic_scores[min(self.critic_i, len(self.critic_scores) - 1)]
            self.critic_i += 1
            out = {"scores": {k: s for k in ["originality", "hook", "story", "dialogue", "pacing", "emotion"]},
                   "notes": [{"scene_id": "1.1", "note": "Sharpen the dialogue"}],
                   "accuracy_issues": self.accuracy_issues}
        else:
            raise AssertionError(f"unexpected prompt: {system[:80]}")
        return json.dumps(out), 100


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ["hn_top", "reddit_top", "youtube_trending", "youtube_search", "wikipedia_search"]:
        monkeypatch.setattr(tools, name, lambda *a, **k: [])
    monkeypatch.setattr(tools, "wikipedia_extract", lambda *a, **k: None)


def make(**fake_kw):
    cfg = load_settings(pathlib.Path(__file__).parent.parent / "config" / "settings.yaml")
    cfg["film"].update({"min_minutes": 1, "max_minutes": 60})
    fake = FakeBackend(**fake_kw)
    llm = LLMRouter(cfg, backends={"fast": (fake, "f"), "smart": (fake, "s")})
    return cfg, llm, fake


def with_sources(monkeypatch):
    monkeypatch.setattr(tools, "wikipedia_search", lambda q, n=5: [{"title": "Clock"}, {"title": "Other"}])
    monkeypatch.setattr(tools, "wikipedia_extract", lambda t, max_chars=3500: {"title": t, "url": f"https://x/{t}", "text": "A clock tells time."})


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
    assert state.concept["title"] == "The Clock"  # concept with no cast is dropped
    assert abs(state.script_scores["dialogue_share"] - 0.25) < 0.01


def test_speakers_are_normalised():
    cfg, llm, fake = make(critic_scores=(9,))
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    speakers = {ln["speaker"] for s in state.scenes for ln in s["lines"]}
    assert speakers == {"NARRATOR", "Mara"}


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
    report = (state.dir / "report.md").read_text()
    assert "Open critic notes" in report and "Read before use" in report


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
    cfg2, llm2, _ = make(critic_scores=(9,))
    cfg2["film"].update({"min_minutes": 12, "max_minutes": 15})
    short = run_pipeline(RunState(mode="topic", topic="x"), llm2, cfg2)
    assert not short.script_passed
    assert any("Runtime" in n["note"] for n in short.critic_notes)


def test_rewrite_touches_only_flagged_scenes():
    cfg, llm, fake = make(critic_scores=(5, 9))
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    # 4 scenes in the first draft, then only scene 1.1 is rewritten
    assert fake.scene_calls == 5
    assert state.script_rounds == 2


def test_worse_rewrite_reverts_to_best_draft():
    cfg, llm, fake = make(critic_scores=(7, 5, 5))
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    assert not state.script_passed
    assert state.script_scores["average"] == 7.0
    assert state.scenes[0]["lines"][0]["visual"] == "v1"  # first draft of scene 1.1 survived


def test_accuracy_issue_blocks_pass_even_with_high_scores():
    cfg, llm, fake = make(critic_scores=(9,), accuracy_issues=[{"scene_id": "1.2", "issue": "invents a quote for a real person"}])
    state = run_pipeline(RunState(mode="topic", topic="x"), llm, cfg)
    assert not state.script_passed
    assert any("ACCURACY" in n["note"] for n in state.critic_notes)


def test_sensitive_topic_and_missing_sources_are_flagged():
    cfg, llm, fake = make(critic_scores=(9,), sensitive=True)
    state = run_pipeline(RunState(mode="topic", topic="a living religion"), llm, cfg)
    text = " ".join(state.warnings)
    assert "real people" in text and "No web sources" in text and "Originality was not checked" in text
    assert "Read before use" in (state.dir / "report.md").read_text()


def test_unsupported_dossier_claims_are_removed(monkeypatch):
    with_sources(monkeypatch)
    dossier = "## Core facts\n- A fact [S1]\n- Group X recruited children as a strategy [S1]\n## Open questions\n- none"
    cfg, llm, fake = make(critic_scores=(9,), dossier=dossier, unsupported=["Group X recruited children as a strategy [S1]"])
    state = run_pipeline(RunState(mode="topic", topic="clocks"), llm, cfg)
    assert "recruited" not in state.dossier
    assert "A fact" in state.dossier and "## Sources" in state.dossier
    assert "https://x/Clock" in state.dossier and "https://x/Other" not in state.dossier  # source filter kept only Clock


def test_hard_checks_catch_bad_speakers_monologues_and_missing_dialogue():
    cfg, _, _ = make()
    state = RunState(mode="topic", topic="x")
    state.concept = {"characters": [{"name": "Mara Vale"}, {"name": "Jon"}]}
    state.beat_sheet = {"acts": [{"scenes": [
        {"scene_id": "1.1", "form": "mixed"}, {"scene_id": "1.2", "form": "narration"}, {"scene_id": "1.3", "form": "mixed"}]}]}
    long = " ".join(["w"] * 80)
    state.scenes = [
        {"scene_id": "1.1", "lines": [{"speaker": "Zed", "text": "hi"}, {"speaker": "Mara Vale", "text": long}]},
        {"scene_id": "1.2", "lines": [{"speaker": "Jon", "text": "hello"}]},
        {"scene_id": "1.3", "lines": []},
    ]
    notes, share = hard_checks(state, cfg)
    text = " | ".join(n["note"] for n in notes)
    assert "Unknown speakers" in text and "80 words" in text and "narration only" in text and "no lines" in text
    assert share > 0.8


def test_canonical_speaker_and_scene_normalising():
    cast = ["Mara Vale", "Jon"]
    assert canonical_speaker("mara", cast) == "Mara Vale"
    assert canonical_speaker("Narration", cast) == "NARRATOR"
    assert canonical_speaker("", cast) == "UNKNOWN"
    scene = normalize_scene([{"speaker": "JON", "text": " hi "}, {"speaker": "Jon", "text": ""}, "junk"], cast)
    assert scene["lines"] == [{"speaker": "Jon", "text": "hi", "visual": "", "emotion": ""}]


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
