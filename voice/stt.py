"""Speech-to-text (owner: P1). Implements interfaces.SpeechToText.

TODO(P1): OpenAI transcription with model ACCEX_STT_MODEL (default gpt-4o-mini-transcribe,
fallback whisper-1), language="en", short timeout. Send clip.wav_bytes as an in-memory
file (("speech.wav", bytes)). API/network errors -> AccexError("I couldn't understand
the audio service. Please try again.").
"""
from __future__ import annotations

from interfaces import AudioClip


class OpenAISTT:
    def __init__(self) -> None:
        raise NotImplementedError("voice.OpenAISTT (P1) - run with --mock voice")

    def transcribe(self, clip: AudioClip) -> str:
        raise NotImplementedError
