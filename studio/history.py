"""Remembers recent genres so open-genre discovery rotates instead of repeating."""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("runs") / "history.json"


def recent_genres(n: int) -> list[str]:
    if not PATH.exists():
        return []
    try:
        return json.loads(PATH.read_text(encoding="utf-8")).get("genres", [])[-n:]
    except (json.JSONDecodeError, OSError):
        return []


def record_genre(genre: str) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"genres": []}
    if PATH.exists():
        try:
            data = json.loads(PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    data.setdefault("genres", []).append(genre)
    PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
