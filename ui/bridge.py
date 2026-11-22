"""Bridge from the assistant to the glass pill (no GUI imports here, so it is testable).

- UiBridge: thread-safe event queue. A sender thread delivers events to the page with
  a `deliver(js)` callable (window.evaluate_js); events emitted before the page is ready
  are buffered. emit() never blocks the assistant and never raises.
- TapLog wraps the assistant's EventLog and TapSpeaker wraps its Speaker: they forward
  every call unchanged and copy what the pill needs (events, cues) to the bridge.
"""
from __future__ import annotations

import json
import queue
import threading
from typing import Any, Callable

from interfaces import Cue, EventLog, Speaker

# Only these events reach the pill (no raw model JSON, no images, no keys).
UI_EVENTS = {"transcript", "say", "action", "action_result", "task_end", "confirm",
             "error", "latency", "hello", "cue", "stop"}
MAX_TEXT = 300


def _safe(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k in ("raw",):
            continue
        if isinstance(v, str):
            out[k] = v[:MAX_TEXT]
        elif isinstance(v, (int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict):
            out[k] = {str(a): (b[:MAX_TEXT] if isinstance(b, str) else b)
                      for a, b in list(v.items())[:8]
                      if isinstance(b, (str, int, float, bool)) or b is None}
    return out


def to_js(kind: str, data: dict[str, Any]) -> str:
    payload = json.dumps({"kind": kind, **_safe(data)}, ensure_ascii=False)
    return f"window.accex && window.accex.push({payload})"


class UiBridge:
    def __init__(self) -> None:
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._ready = threading.Event()
        self._deliver: Callable[[str], Any] | None = None
        self._thread = threading.Thread(target=self._run, name="accex-ui", daemon=True)
        self._thread.start()

    def attach(self, deliver: Callable[[str], Any]) -> None:
        """Call once the page has loaded; buffered events are then sent in order."""
        self._deliver = deliver
        self._ready.set()

    def emit(self, kind: str, **data: Any) -> None:
        if kind not in UI_EVENTS:
            return
        try:
            self._queue.put_nowait(to_js(kind, data))
        except Exception:
            pass

    def close(self) -> None:
        self._queue.put(None)

    def _run(self) -> None:
        self._ready.wait()
        while True:
            js = self._queue.get()
            if js is None:
                return
            try:
                self._deliver(js)          # type: ignore[misc]
            except Exception:
                pass                       # the window may be closing; never crash


class TapLog:
    """EventLog that also feeds the pill."""

    def __init__(self, inner: EventLog, bridge: UiBridge) -> None:
        self.inner, self.bridge = inner, bridge

    def log(self, event: str, **data: Any) -> None:
        self.inner.log(event, **data)
        self.bridge.emit(event, **data)

    def __getattr__(self, name: str) -> Any:   # e.g. tests reading .events
        return getattr(self.inner, name)


class TapSpeaker:
    """Speaker that also tells the pill about cues and barge-in."""

    def __init__(self, inner: Speaker, bridge: UiBridge) -> None:
        self.inner, self.bridge = inner, bridge

    def say(self, text: str) -> None:
        self.inner.say(text)

    def stop(self) -> None:
        self.inner.stop()
        self.bridge.emit("stop")

    def wait(self, timeout: float | None = None) -> None:
        self.inner.wait(timeout)

    def cue(self, name: Cue) -> None:
        self.inner.cue(name)
        self.bridge.emit("cue", name=name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)
