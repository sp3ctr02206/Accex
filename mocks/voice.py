"""Mock voice (owner: P1). Type instead of talking, print instead of speaking.

A typed line travels inside AudioClip.wav_bytes as UTF-8 with duration_s == 0,
and ConsoleSTT decodes it back. Real audio clips are never produced here.
"""
from __future__ import annotations

from typing import Callable

from interfaces import AudioClip, Cue


def _text_clip(text: str) -> AudioClip:
    return AudioClip(wav_bytes=text.encode("utf-8"), duration_s=0.0)


class ConsoleListener:
    """Each line typed in the terminal is one push-to-talk utterance."""

    def wait_for_utterance(self, on_start: Callable[[], None] | None = None) -> AudioClip:
        line = input("\nYou (type and press Enter, Ctrl+C to quit) > ")  # EOFError ends the loop
        if on_start:
            on_start()
        return _text_clip(line)


class ScriptedListener:
    """Feeds a fixed list of utterances (for tests); raises EOFError when exhausted."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = list(lines)

    def wait_for_utterance(self, on_start: Callable[[], None] | None = None) -> AudioClip:
        if not self.lines:
            raise EOFError("script finished")
        if on_start:
            on_start()
        return _text_clip(self.lines.pop(0))


class ConsoleSTT:
    """Decodes text clips from the mock listeners; real audio gets a fixed question."""

    def transcribe(self, clip: AudioClip) -> str:
        if clip.duration_s == 0.0:
            return clip.wav_bytes.decode("utf-8", errors="replace").strip()
        return "What's on my screen?"


class PrintSpeaker:
    """Prints speech and cues; keeps them in lists so tests can assert on them."""

    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self.said: list[str] = []
        self.cues: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)
        if not self.quiet:
            print(f"[SAY] {text}")

    def stop(self) -> None:
        pass

    def wait(self, timeout: float | None = None) -> None:
        pass

    def cue(self, name: Cue) -> None:
        self.cues.append(name)
        if not self.quiet:
            print(f"[CUE] {name}")


def create_listener() -> ConsoleListener:
    return ConsoleListener()


def create_stt() -> ConsoleSTT:
    return ConsoleSTT()


def create_speaker() -> PrintSpeaker:
    return PrintSpeaker()
