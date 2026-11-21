"""Mock event log (owner: P3). Prints events and keeps them in memory."""
from __future__ import annotations

from typing import Any


class PrintLog:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self.events: list[tuple[str, dict[str, Any]]] = []

    def log(self, event: str, **data: Any) -> None:
        self.events.append((event, data))
        if not self.quiet:
            fields = " ".join(f"{k}={v!r}" for k, v in data.items())
            print(f"[LOG] {event} {fields}")


def create_log() -> PrintLog:
    return PrintLog()
