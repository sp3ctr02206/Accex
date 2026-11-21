"""Push-to-talk listener (owner: P1). Implements interfaces.Listener.

TODO(P1), see PLAN.md > Person 1:
- pynput keyboard listener for ACCEX_HOTKEY (default ctrl_r) pushes press/release
  events into a queue.Queue; wait_for_utterance() consumes them on the caller's thread
  and calls on_start() there when the key goes down.
- sounddevice.InputStream (16 kHz, mono, int16, device ACCEX_MIC_DEVICE) appends
  frames while the key is held; build the WAV in a BytesIO with the `wave` module.
- Taps shorter than 0.3 s: call on_start() (stops speech) but keep waiting.
- Mic errors -> AccexError("I can't access the microphone.").
"""
from __future__ import annotations

from typing import Callable

from interfaces import AudioClip


class PushToTalkListener:
    def __init__(self) -> None:
        raise NotImplementedError("voice.PushToTalkListener (P1) - run with --mock voice")

    def wait_for_utterance(self, on_start: Callable[[], None] | None = None) -> AudioClip:
        raise NotImplementedError
