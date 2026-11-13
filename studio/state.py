"""Shared run state. Every agent reads and writes this object, never talks to another agent."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class RunState(BaseModel):
    run_id: str = Field(default_factory=lambda: time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4])
    mode: Literal["discover", "topic"] = "topic"
    topic: Optional[str] = None

    # discover mode
    signals: list[dict] = Field(default_factory=list)
    opportunities: list[dict] = Field(default_factory=list)
    chosen_opportunity: Optional[dict] = None

    # research and concept
    dossier: str = ""
    concepts: list[dict] = Field(default_factory=list)
    concept: Optional[dict] = None
    concept_regenerations: int = 0

    # story and script
    beat_sheet: Optional[dict] = None
    scenes: list[dict] = Field(default_factory=list)   # each: scene dict with "lines"
    script_scores: dict = Field(default_factory=dict)
    script_score: float = 0.0
    critic_notes: list[dict] = Field(default_factory=list)
    script_rounds: int = 0
    script_passed: bool = False

    # bookkeeping
    tokens_used: int = 0
    status: str = "created"
    log: list[str] = Field(default_factory=list)

    def note(self, msg: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log.append(f"[{stamp}] {msg}")
        print(f"  {msg}")

    @property
    def dir(self) -> Path:
        return Path("runs") / self.run_id

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "state.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, run_id: str) -> "RunState":
        path = Path("runs") / run_id / "state.json"
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
