"""Hard checks that run in code. The model cannot talk its way past these."""
from __future__ import annotations

import re

NARRATOR = "NARRATOR"
_NARRATOR_ALIASES = {"narrator", "narration", "voiceover", "voice over", "voice-over", "v.o.", "vo"}


def cast_names(state) -> list[str]:
    return [str(c["name"]).strip() for c in (state.concept or {}).get("characters", []) if c.get("name")]


def canonical_speaker(name: str, cast: list[str]) -> str:
    n = re.sub(r"\s+", " ", name or "").strip()
    if not n:
        return "UNKNOWN"
    low = n.lower()
    if low in _NARRATOR_ALIASES:
        return NARRATOR
    for c in cast:
        cl = c.lower()
        if low == cl or low == cl.split()[0] or cl == low.split()[0]:
            return c
    return n


def normalize_scene(raw, cast: list[str]) -> dict:
    """Coerce whatever the model returned into {"lines": [{speaker, text, visual, emotion}]}."""
    if isinstance(raw, list):
        raw = {"lines": raw}
    if not isinstance(raw, dict):
        raw = {}
    lines = []
    for ln in raw.get("lines") or []:
        if not isinstance(ln, dict):
            continue
        text = str(ln.get("text", "")).strip()
        if not text:
            continue
        lines.append(
            {
                "speaker": canonical_speaker(str(ln.get("speaker", "")), cast),
                "text": text,
                "visual": str(ln.get("visual", "")),
                "emotion": str(ln.get("emotion", "")),
            }
        )
    raw["lines"] = lines
    return raw


def hard_checks(state, cfg: dict) -> tuple[list[dict], float]:
    """Return (notes, dialogue_share). Any note means the script fails the gate."""
    q = cfg["quality"]
    cast = cast_names(state)
    valid = set(cast) | {NARRATOR}
    forms = {s["scene_id"]: s.get("form", "mixed") for a in state.beat_sheet.get("acts", []) for s in a.get("scenes", [])}
    notes: list[dict] = []
    char_words = total_words = 0

    for sc in state.scenes:
        sid = sc["scene_id"]
        lines = sc.get("lines", [])
        if not lines:
            notes.append({"scene_id": sid, "note": "Scene has no lines. Write it in full.", "hard": True})
            continue

        bad = sorted({ln["speaker"] for ln in lines if ln["speaker"] not in valid})
        if bad:
            notes.append({"scene_id": sid, "note": f"Unknown speakers {bad}. Use only NARRATOR or these cast names: {cast}.", "hard": True})

        char_lines = [ln for ln in lines if ln["speaker"] != NARRATOR]
        for ln in lines:
            n = len(ln["text"].split())
            total_words += n
            if ln["speaker"] != NARRATOR:
                char_words += n

        long_line = next(
            (ln for ln in lines if ln["speaker"] != NARRATOR and len(ln["text"].split()) > q["max_character_line_words"]),
            None,
        )
        if long_line:
            notes.append(
                {
                    "scene_id": sid,
                    "note": f"{long_line['speaker']} has a speech of {len(long_line['text'].split())} words. Characters speak in short exchanges (under {q['max_character_line_words']} words a line). Move inner thoughts to NARRATOR lines or split into dialogue.",
                    "hard": True,
                }
            )
        long_narr = next(
            (ln for ln in lines if ln["speaker"] == NARRATOR and len(ln["text"].split()) > q["max_narrator_line_words"]),
            None,
        )
        if long_narr:
            notes.append({"scene_id": sid, "note": f"A narrator line is {len(long_narr['text'].split())} words. Split narration into lines under {q['max_narrator_line_words']} words.", "hard": True})

        form = forms.get(sid, "mixed")
        if form == "narration" and char_lines:
            notes.append({"scene_id": sid, "note": "This scene is planned as narration only. Every line must be NARRATOR.", "hard": True})
        if form in ("dialogue", "mixed") and len(char_lines) < 2:
            notes.append({"scene_id": sid, "note": f"This scene is planned as {form} but has fewer than 2 character lines. Add a real exchange between characters.", "hard": True})

    share = char_words / total_words if total_words else 0.0
    if total_words and not (q["dialogue_share_min"] <= share <= q["dialogue_share_max"]):
        direction = "Add more character dialogue" if share < q["dialogue_share_min"] else "Add more narration and cut dialogue"
        notes.append(
            {
                "scene_id": "ALL",
                "note": f"Character dialogue is {share:.0%} of spoken words, target {q['dialogue_share_min']:.0%}-{q['dialogue_share_max']:.0%}. {direction}.",
                "hard": True,
            }
        )
    return notes, round(share, 3)
