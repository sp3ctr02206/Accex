"""Demo package (owner: Person 3): event log, demo screens, demo checklist."""
from __future__ import annotations


def create_log():
    from .log import JsonlEventLog
    return JsonlEventLog()
