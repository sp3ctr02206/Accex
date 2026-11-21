"""Earcons (owner: P1): four short, distinct, non-verbal tones.

Tones are numpy sine waves with a short fade in/out (no clicks), generated once and
played with sounddevice.play (non-blocking). Nothing is ever written to disk.
"""
from __future__ import annotations

import numpy as np

SAMPLE_RATE = 44100
VOLUME = 0.25

# Each cue is a sequence of (frequency Hz, duration s); 0 Hz = silence.
PATTERNS: dict[str, list[tuple[float, float]]] = {
    "listening": [(660, 0.06), (880, 0.08)],               # rising: "go ahead"
    "thinking":  [(520, 0.09)],                            # single soft blip
    "done":      [(880, 0.06), (1320, 0.10)],              # high rising: success
    "error":     [(300, 0.11), (0, 0.04), (220, 0.16)],    # low falling double
}


def _tone(freq: float, dur: float, rate: int) -> np.ndarray:
    n = int(rate * dur)
    if freq <= 0:
        return np.zeros(n, dtype=np.float32)
    t = np.arange(n, dtype=np.float32) / rate
    wave = np.sin(2 * np.pi * freq * t)
    fade = min(n // 2, int(rate * 0.008))
    if fade:
        env = np.ones(n, dtype=np.float32)
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        env[:fade], env[-fade:] = ramp, ramp[::-1]
        wave *= env
    return (wave * VOLUME).astype(np.float32)


def make_cue(name: str, rate: int = SAMPLE_RATE) -> np.ndarray:
    """Float32 mono samples for one cue. KeyError for unknown names."""
    return np.concatenate([_tone(f, d, rate) for f, d in PATTERNS[name]])


class CuePlayer:
    """Plays cues without blocking. Failures are swallowed: a missing beep must never
    break a turn (speech still carries the message)."""

    def __init__(self, rate: int = SAMPLE_RATE) -> None:
        self.rate = rate
        self._cache = {name: make_cue(name, rate) for name in PATTERNS}

    def play(self, name: str) -> None:
        samples = self._cache.get(name)
        if samples is None:
            return
        try:
            import sounddevice as sd
            sd.play(samples, self.rate)
        except Exception:
            pass
