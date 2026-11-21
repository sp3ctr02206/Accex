"""Speech-to-text (owner: P1). Implements interfaces.SpeechToText.

OpenAI transcription with ACCEX_STT_MODEL (default gpt-4o-mini-transcribe), falling back
to whisper-1 if the primary model is rejected. The WAV is sent as an in-memory file.
Near-silent clips return '' without an API call (avoids "Thank you." hallucinations).
"""
from __future__ import annotations

import io
import os
import wave

import numpy as np

from interfaces import AccexError, AudioClip

FALLBACK_MODEL = "whisper-1"
# Steers spelling of names the user says to the assistant (otherwise "Access", "Actus").
VOCABULARY_HINT = "Accex, open Gmail, YouTube, Spotify, Discord, scroll down."
SERVICE_ERROR = "I couldn't understand the audio service. Please try again."


def clip_rms(clip: AudioClip) -> float:
    """RMS level of a 16-bit WAV clip (0..32768). 0.0 if it can't be decoded."""
    try:
        with wave.open(io.BytesIO(clip.wav_bytes), "rb") as w:
            pcm = w.readframes(w.getnframes())
    except Exception:
        return 0.0
    samples = np.frombuffer(pcm, dtype=np.int16)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


class OpenAISTT:
    def __init__(self, model: str | None = None, client=None) -> None:
        self.model = model or os.getenv("ACCEX_STT_MODEL", "gpt-4o-mini-transcribe")
        self.timeout = float(os.getenv("ACCEX_STT_TIMEOUT", "10"))
        self.min_rms = float(os.getenv("ACCEX_STT_MIN_RMS", "60"))
        import openai
        self._openai = openai
        if client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise AccexError("My speech recognition key is missing. Please check the setup.",
                                 "OPENAI_API_KEY is not set")
            client = openai.OpenAI(timeout=self.timeout, max_retries=1)
        self.client = client

    def transcribe(self, clip: AudioClip) -> str:
        if clip.duration_s < 0.2 or clip_rms(clip) < self.min_rms:
            return ""
        try:
            return self._call(self.model, clip)
        except self._openai.APIStatusError as e:
            # Model unavailable / rejected the request: try the older model once.
            if self.model == FALLBACK_MODEL or e.status_code in (401, 429):
                raise self._error(e) from e
            try:
                return self._call(FALLBACK_MODEL, clip)
            except Exception as e2:
                raise self._error(e2) from e2
        except Exception as e:
            raise self._error(e) from e

    def _call(self, model: str, clip: AudioClip) -> str:
        resp = self.client.audio.transcriptions.create(
            model=model, file=("speech.wav", clip.wav_bytes, "audio/wav"),
            language="en", prompt=VOCABULARY_HINT, timeout=self.timeout)
        text = resp if isinstance(resp, str) else getattr(resp, "text", "")
        return (text or "").strip()

    def _error(self, e: Exception) -> AccexError:
        o = self._openai
        if isinstance(e, o.APITimeoutError):
            return AccexError("Speech recognition is taking too long. Please try again.", repr(e))
        if isinstance(e, o.APIConnectionError):
            return AccexError("I can't reach the internet right now.", repr(e))
        if isinstance(e, o.AuthenticationError):
            return AccexError("My speech recognition key isn't working. Please check the setup.",
                              repr(e))
        return AccexError(SERVICE_ERROR, repr(e))
