"""UI bridge and taps (no GUI needed)."""
from __future__ import annotations

import json
import time

from main import Assistant
from mocks.actions import KeywordGate, LoggingExecutor
from mocks.brain import ScriptedBrain, StaticCapturer
from mocks.demo import PrintLog
from mocks.voice import ConsoleSTT, PrintSpeaker, ScriptedListener
from ui.bridge import MAX_TEXT, TapLog, TapSpeaker, UiBridge, to_js


def payloads(sent):
    return [json.loads(js[js.index("(") + 1:-1]) for js in sent]


def wait_for(sent, n, timeout=2.0):
    end = time.monotonic() + timeout
    while len(sent) < n and time.monotonic() < end:
        time.sleep(0.01)


def test_to_js_drops_raw_and_trims_text():
    js = to_js("llm", {"raw": "secret model json", "say": "x" * 1000, "params": {"url": "u"}})
    data = json.loads(js[js.index("(") + 1:-1])
    assert "raw" not in data and len(data["say"]) == MAX_TEXT and data["kind"] == "llm"
    assert js.startswith("window.accex && window.accex.push(")


def test_events_before_attach_are_buffered_in_order():
    b = UiBridge()
    b.emit("transcript", text="hello")
    b.emit("say", text="hi")
    b.emit("unknown_event", x=1)           # filtered out
    sent = []
    b.attach(sent.append)
    wait_for(sent, 2)
    assert [p["kind"] for p in payloads(sent)] == ["transcript", "say"]


def test_deliver_errors_never_reach_the_assistant():
    b = UiBridge()
    calls = []

    def boom(js):
        calls.append(js)
        raise RuntimeError("window closed")

    b.attach(boom)
    b.emit("say", text="a")
    b.emit("say", text="b")
    wait_for(calls, 2)
    assert len(calls) == 2


def test_taps_forward_and_mirror_a_full_task():
    sent = []
    bridge = UiBridge()
    bridge.attach(sent.append)
    executor = LoggingExecutor(quiet=True)
    inner_speaker, inner_log = PrintSpeaker(quiet=True), PrintLog(quiet=True)
    a = Assistant(listener=ScriptedListener(["Play Money for Nothing on Spotify"]),
                  stt=ConsoleSTT(), speaker=TapSpeaker(inner_speaker, bridge),
                  capturer=StaticCapturer(), brain=ScriptedBrain(executor.specs()),
                  executor=executor, gate=KeywordGate(), log=TapLog(inner_log, bridge),
                  settle_scale=0)
    a.run_turn()
    assert len(executor.executed) == 4                       # behaviour unchanged
    assert inner_speaker.said[-1] == "Money for Nothing by Dire Straits is playing."
    end = time.monotonic() + 2
    while not any('"task_end"' in js for js in sent) and time.monotonic() < end:
        time.sleep(0.01)
    time.sleep(0.05)
    kinds = [p["kind"] for p in payloads(sent)]
    assert kinds[:3] == ["stop", "cue", "cue"]               # key down, listening, thinking
    assert kinds.count("action") == 4 and kinds[-1] == "task_end"
    assert "llm" not in kinds                                 # raw model output stays private
