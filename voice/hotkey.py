"""Push-to-talk listener (owner: P1). Implements interfaces.Listener.

Threads:
- pynput listener thread: key down/up for ACCEX_HOTKEY (default ctrl_r). It starts and
  stops the recording buffer itself (so audio is never lost while the main thread is
  busy) and pushes ("down", t) / ("up", t, pcm) events into a queue.Queue.
- PortAudio callback thread: appends int16 frames while recording; keeps a ~0.15 s
  pre-roll so the first syllable is not clipped.
- Caller thread: wait_for_utterance() consumes the queue, calls on_start() on key down,
  ignores taps < 0.3 s, and returns the utterance as an in-memory WAV.

The microphone stream stays open (frames are dropped unless the key is held) so there is
no device-open delay at key down. Audio lives in memory only.
"""
from __future__ import annotations

import collections
import io
import os
import queue
import threading
import time
import wave
from typing import Callable

from interfaces import AccexError, AudioClip

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2          # int16
MIN_UTTERANCE_S = 0.3     # shorter presses are taps (they only silence speech)
MAX_UTTERANCE_S = 60.0    # safety cap on held-key recordings
PREROLL_S = 0.15
MIC_ERROR = "I can't access the microphone."


def build_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    """Wrap raw 16-bit mono PCM in a WAV container, in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def is_tap(duration_s: float) -> bool:
    return duration_s < MIN_UTTERANCE_S


def parse_hotkey(name: str):
    """pynput key for a name like 'ctrl_r', 'f9' or 'a'. ValueError if unknown."""
    from pynput import keyboard
    name = (name or "ctrl_r").strip().lower()
    if name in ("insert", "caps_lock"):
        raise ValueError(f"{name} is an NVDA modifier; pick another ACCEX_HOTKEY")
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown ACCEX_HOTKEY: {name!r}")


def _mic_device() -> int | str | None:
    raw = os.getenv("ACCEX_MIC_DEVICE", "").strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw


class PushToTalkListener:
    def __init__(self, hotkey: str | None = None, device: int | str | None = None,
                 rate: int = SAMPLE_RATE, start: bool = True) -> None:
        self.rate = rate
        self.hotkey_name = hotkey or os.getenv("ACCEX_HOTKEY", "ctrl_r")
        self.device = device if device is not None else _mic_device()
        self.events: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._down = False
        self._t_down = 0.0
        self._chunks: list[bytes] = []
        self._rec_bytes = 0
        self._preroll: collections.deque[bytes] = collections.deque()
        self._preroll_frames = 0
        self._mic_status: str | None = None
        self._stream = None
        self._kb = None
        self._key = None
        if start:
            self._start()

    # ------------------------------------------------------------ setup
    def _start(self) -> None:
        try:
            self._key = parse_hotkey(self.hotkey_name)
        except ValueError as e:
            raise AccexError("My push-to-talk key is not set up correctly.", str(e)) from e
        self._open_mic()
        from pynput import keyboard
        self._kb = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._kb.daemon = True
        self._kb.start()

    def _open_mic(self) -> None:
        try:
            import sounddevice as sd
            self._stream = sd.RawInputStream(
                samplerate=self.rate, channels=CHANNELS, dtype="int16",
                device=self.device, blocksize=0, callback=self._on_audio)
            self._stream.start()
        except Exception as e:
            self._stream = None
            raise AccexError(MIC_ERROR, f"mic open failed (device={self.device!r}): {e!r}") from e

    def close(self) -> None:
        if self._kb is not None:
            self._kb.stop()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ------------------------------------------------------------ pynput thread
    def _matches(self, key) -> bool:
        if key == self._key:
            return True
        # Character keys: compare by char so shift/layout differences don't matter.
        kc = getattr(key, "char", None)
        want = getattr(self._key, "char", None)
        return kc is not None and want is not None and kc.lower() == want.lower()

    def _on_press(self, key) -> None:
        if self._matches(key):
            self.key_down()

    def _on_release(self, key) -> None:
        if self._matches(key):
            self.key_up()

    def interrupted(self) -> bool:
        """True while the key is held or a key-down is waiting to be consumed.

        Only peeks; wait_for_utterance() still receives the events. main.py polls this
        to stop a multi-step task as soon as the user presses the key."""
        with self._lock:
            if self._down:
                return True
        with self.events.mutex:
            return any(e[0] == "down" for e in self.events.queue)

    def key_down(self, t: float | None = None) -> None:
        """Start recording. Auto-repeat presses while held are ignored."""
        t = time.perf_counter() if t is None else t
        with self._lock:
            if self._down:
                return
            self._down = True
            self._t_down = t
            self._chunks = list(self._preroll)
            self._rec_bytes = sum(len(c) for c in self._chunks)
        self.events.put(("down", t))

    def key_up(self, t: float | None = None) -> None:
        t = time.perf_counter() if t is None else t
        with self._lock:
            if not self._down:
                return
            self._down = False
            pcm = b"".join(self._chunks)
            self._chunks = []
            duration = t - self._t_down
        self.events.put(("up", duration, pcm))

    # ------------------------------------------------------------ audio thread
    def _on_audio(self, indata, frames, time_info, status) -> None:
        data = bytes(indata)
        with self._lock:
            if status:
                self._mic_status = str(status)
            if self._down and self._rec_bytes < self.rate * MAX_UTTERANCE_S * SAMPLE_WIDTH:
                self._chunks.append(data)
                self._rec_bytes += len(data)
            self._preroll.append(data)
            self._preroll_frames += frames
            limit = int(self.rate * PREROLL_S)
            while self._preroll and self._preroll_frames - len(self._preroll[0]) // SAMPLE_WIDTH >= limit:
                self._preroll_frames -= len(self._preroll.popleft()) // SAMPLE_WIDTH

    # ------------------------------------------------------------ caller thread
    def wait_for_utterance(self, on_start: Callable[[], None] | None = None) -> AudioClip:
        if self._kb is not None and self._stream is None:
            self._open_mic()  # reopen after a device error
        started = False
        while True:
            try:
                event = self.events.get(timeout=0.25)
            except queue.Empty:
                self._check_listener()
                continue
            if event[0] == "down":
                started = True
                if on_start:
                    on_start()
                continue
            _, duration, pcm = event
            if not started and on_start:  # down was consumed by an earlier call
                on_start()
            started = False
            if is_tap(duration):
                continue
            if self._stream is not None and not pcm:
                raise AccexError(MIC_ERROR, f"no audio frames recorded ({self._mic_status})")
            pcm = pcm[: int(self.rate * MAX_UTTERANCE_S) * SAMPLE_WIDTH]
            return AudioClip(wav_bytes=build_wav(pcm, self.rate),
                             duration_s=len(pcm) / (SAMPLE_WIDTH * self.rate))

    def _check_listener(self) -> None:
        if self._kb is not None and not self._kb.is_alive():
            raise AccexError("My push-to-talk key stopped working.", "pynput listener died")
