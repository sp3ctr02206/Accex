"""Voice package (owner: Person 1): push-to-talk, recording, STT, TTS, earcons.

Factories are the only public API (see interfaces.py). Imports are lazy so the rest
of the app runs with `--mock voice` even if voice dependencies are missing.
"""
from __future__ import annotations


def create_listener():
    from .hotkey import PushToTalkListener
    return PushToTalkListener()


def create_stt():
    from .stt import OpenAISTT
    return OpenAISTT()


def create_speaker():
    import os
    if os.getenv("ACCEX_TTS", "sapi").strip().lower() == "elevenlabs":
        from .elevenlabs import ElevenLabsSpeaker
        return ElevenLabsSpeaker()
    from .tts import create_speaker as _create
    return _create()      # ACCEX_TTS: sapi (default) | openai | elevenlabs
