"""Text-to-speech + earcons (owner: P1). Implements interfaces.Speaker.

SapiSpeaker drives Windows SAPI through pywin32. It must be created and used on the main
thread (COM apartment). say() is async + purge, so it returns at once and interrupts any
speech in progress; stop() purges with an empty string.
Do NOT use pyttsx3 (blocking runAndWait, hangs, not interruptible).
"""
from __future__ import annotations

import os

from interfaces import AccexError, Cue

from .cues import CuePlayer

SVSF_ASYNC = 1
SVSF_PURGE = 2
SVSF_IS_NOT_XML = 16     # screen text like "<b>" must be read, not parsed as SAPI XML


class SapiSpeaker:
    def __init__(self, rate: int | None = None, cues: CuePlayer | None = None) -> None:
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            self.voice = win32com.client.Dispatch("SAPI.SpVoice")
        except Exception as e:
            raise AccexError("I can't start the speech engine.", f"SAPI init failed: {e!r}") from e
        if rate is None:
            try:
                rate = int(os.getenv("ACCEX_TTS_RATE", "0"))
            except ValueError:
                rate = 0
        self.voice.Rate = max(-10, min(10, rate))
        self.cues = cues or CuePlayer()

    def say(self, text: str) -> None:
        self.voice.Speak(text, SVSF_ASYNC | SVSF_PURGE | SVSF_IS_NOT_XML)

    def stop(self) -> None:
        try:
            self.voice.Speak("", SVSF_ASYNC | SVSF_PURGE)
        except Exception:
            pass

    def wait(self, timeout: float | None = None) -> None:
        ms = -1 if timeout is None else int(timeout * 1000)
        self.voice.WaitUntilDone(ms)

    def cue(self, name: Cue) -> None:
        self.cues.play(name)
