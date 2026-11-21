"""Text-to-speech + earcons (owner: P1). Implements interfaces.Speaker.

TODO(P1):
- SapiSpeaker: win32com.client.Dispatch("SAPI.SpVoice"), created and used on the main
  thread only. say() = Speak(text, 1 | 2)  (SVSFlagsAsync | SVSFPurgeBeforeSpeak);
  stop() = Speak("", 1 | 2); wait() = WaitUntilDone(ms). Rate from ACCEX_TTS_RATE.
- cue(): short numpy sine tones played with sounddevice.play (non-blocking).
- Do NOT use pyttsx3 (blocking runAndWait, hangs, not interruptible).
- Stretch: OpenAISpeaker (streamed TTS) or speaking through NVDA's controller client.
"""
from __future__ import annotations

from interfaces import Cue


class SapiSpeaker:
    def __init__(self) -> None:
        raise NotImplementedError("voice.SapiSpeaker (P1) - run with --mock voice")

    def say(self, text: str) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def wait(self, timeout: float | None = None) -> None:
        raise NotImplementedError

    def cue(self, name: Cue) -> None:
        raise NotImplementedError
