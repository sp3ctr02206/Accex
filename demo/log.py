"""Event log (owner: P3). Implements interfaces.EventLog.

Basic working version shipped with the skeleton; P3 owns and may extend it.
Writes one JSON object per line to logs/session-<timestamp>.jsonl and, when
ACCEX_DEMO=1, also prints each event to the console. Never stores images or audio.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


class JsonlEventLog:
    def __init__(self) -> None:
        self.echo = os.getenv("ACCEX_DEMO", "0") == "1"
        self.path: Path | None = None
        try:
            LOG_DIR.mkdir(exist_ok=True)
            self.path = LOG_DIR / time.strftime("session-%Y%m%d-%H%M%S.jsonl")
        except OSError:
            self.path = None

    def log(self, event: str, **data: Any) -> None:
        try:
            record = {"t": round(time.time(), 3), "event": event, **data}
            line = json.dumps(record, default=str, ensure_ascii=False)
            if self.path:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            if self.echo:
                print(f"[LOG] {line}", file=sys.stderr)
        except Exception:
            pass  # logging must never break the assistant
