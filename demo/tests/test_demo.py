"""Demo assets: dashboard numbers match the demo answers; log and latency tools work."""
from __future__ import annotations

import json
import re
from pathlib import Path

from demo import latency
from demo.log import JsonlEventLog
from mocks.brain import ScriptedBrain

DASHBOARD = Path(__file__).resolve().parent.parent / "screens" / "dashboard.html"


def bars() -> dict[str, int]:
    html = DASHBOARD.read_text(encoding="utf-8")
    return {m: int(v) for m, v in re.findall(r'data-month="(\w+)" data-sales="(\d+)"', html)}


def test_dashboard_has_12_months():
    assert list(bars()) == ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def test_dashboard_numbers():
    data = bars()
    assert max(data, key=data.get) == "Mar" and data["Mar"] == 142_000
    assert min(data, key=data.get) == "Aug" and data["Aug"] == 61_000
    assert sum(data.values()) == 1_200_000
    assert sorted(data.values())[-2] < 142_000 and sorted(data.values())[1] > 61_000


def test_dashboard_matches_mock_brain_answers():
    brain = ScriptedBrain([])
    assert "March" in brain.ask("highest?", None).say and "142" in brain.ask("highest?", None).say
    assert "August" in brain.ask("lowest?", None).say and "61" in brain.ask("lowest?", None).say
    assert "1.2 million" in brain.ask("screen?", None).say


def test_dashboard_is_offline():
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "<script" not in html and "http" not in html.split("-->", 1)[1]


def test_log_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setattr("demo.log.LOG_DIR", tmp_path)
    log = JsonlEventLog()
    log.log("say", text="hola")
    log.log("latency", stt_ms=1, capture_ms=2, llm_ms=3, total_ms=6)
    log.log("weird", obj=object())  # unserializable values never raise
    lines = log.path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["text"] == "hola" and len(lines) == 3


def test_latency_summary():
    events = [{"event": "latency", "stt_ms": s, "capture_ms": 10, "llm_ms": 1000 + s,
               "total_ms": 1500 + s} for s in (100, 200, 300)]
    events += [{"event": "action_result", "ok": True, "message": "Done."},
               {"event": "action_result", "ok": False, "message": "I don't know how to fly."},
               {"event": "error", "where": "turn", "detail": "boom"}]
    text = latency.summarize(events)
    assert "turns: 3" in text and "actions: 1/2 ok" in text and "errors: 1" in text
    assert re.search(r"total_ms\s+1700", text)
