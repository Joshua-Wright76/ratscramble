from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class GameLogger:
    root: str
    game_id: str
    run_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = Path(self.root) / f"{ts}_{self.game_id}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self.run_dir / "events.jsonl"
        self._llm_path = self.run_dir / "raw_llm.jsonl"
        self._transcript_path = self.run_dir / "transcript.md"
        self._lock = threading.Lock()

    def log_event(self, event_type: str, round_number: int, phase: str, payload: dict[str, Any]) -> None:
        self._write_jsonl(
            self._events_path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": event_type,
                "round": round_number,
                "phase": phase,
                "payload": payload,
            },
        )

    def log_llm(
        self,
        role: str,
        player: str,
        prompt: dict[str, Any],
        response_text: str,
        raw_response: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._write_jsonl(
            self._llm_path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "player": player,
                "prompt": prompt,
                "response_text": response_text,
                "raw_response": raw_response,
                "metadata": metadata or {},
            },
        )

    def log_transcript_line(self, line: str) -> None:
        with self._lock:
            with self._transcript_path.open("a", encoding="utf-8") as handle:
                handle.write(f"- {line}\n")

    def _write_jsonl(self, path: Path, obj: dict[str, Any]) -> None:
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def run_path(self) -> str:
        return str(self.run_dir)
