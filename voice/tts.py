"""Text-to-speech + earcons (owner: P1). Implements interfaces.Speaker.

SapiSpeaker drives Windows SAPI through pywin32. It must be created and used on the main
thread (COM apartment). say() is async + purge, so it returns at once and interrupts any
speech in progress; stop() purges with an empty string.
Do NOT use pyttsx3 (blocking runAndWait, hangs, not interruptible).

OpenAISpeaker (ACCEX_TTS=openai) streams OpenAI TTS as raw PCM and plays it while it
downloads; it falls back to SAPI if the API fails.
"""
from __future__ import annotations

import os
import time

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


# ---------------------------------------------------------------- OpenAI (streamed)
TTS_RATE = 24000          # OpenAI "pcm" format: 24 kHz, 16-bit, mono, little-endian
CHUNK_BYTES = 2400        # 50 ms per write, so stop() takes effect within ~50 ms
DEFAULT_INSTRUCTIONS = ("Speak clearly, warmly and a little briskly, like a helpful "
                        "screen reader. Read numbers carefully.")


class OpenAISpeaker:
    """Streamed OpenAI TTS played as it downloads (ACCEX_TTS=openai).

    One worker thread owns the HTTP stream and the audio output; say()/stop() only bump
    a generation counter and enqueue text, so they return immediately on the caller's
    thread. If the API fails, the worker speaks the same text through its own SAPI voice
    (COM initialised on the worker thread) when available, so the user still hears it.
    """

    def __init__(self, client=None, model: str | None = None, voice: str | None = None,
                 cues: CuePlayer | None = None, output=None, fallback=None) -> None:
        import queue
        import threading
        self.model = model or os.getenv("ACCEX_TTS_MODEL", "gpt-4o-mini-tts")
        self.voice = voice or os.getenv("ACCEX_TTS_VOICE", "coral")
        self.instructions = os.getenv("ACCEX_TTS_INSTRUCTIONS", DEFAULT_INSTRUCTIONS)
        self.timeout = float(os.getenv("ACCEX_TTS_TIMEOUT", "10"))
        if client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise AccexError("My voice key is missing. Please check the setup.",
                                 "OPENAI_API_KEY is not set")
            import openai
            client = openai.OpenAI(timeout=self.timeout, max_retries=0)
        self.client = client
        self.cues = cues or CuePlayer()
        self._output = output            # tests inject a fake; None = sounddevice
        self._fallback = fallback        # tests inject a fake; None = lazy SAPI
        self._fallback_failed = False
        self._gen = 0
        self._lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue()
        self._idle = threading.Event()
        self._idle.set()
        self._busy = False
        self._played = False
        self.last_error: Exception | None = None
        self._worker = threading.Thread(target=self._run, name="accex-tts", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------ Speaker API
    def say(self, text: str) -> None:
        text = (text or "").strip()
        with self._lock:
            self._gen += 1
            self._drain()
            if not text:
                return
            self._idle.clear()
            self._queue.put((self._gen, text))

    def stop(self) -> None:
        with self._lock:
            self._gen += 1
            self._drain()

    def wait(self, timeout: float | None = None) -> None:
        self._idle.wait(timeout)

    def cue(self, name: Cue) -> None:
        self.cues.play(name)

    def close(self) -> None:
        self.stop()
        self._queue.put(None)

    # ------------------------------------------------------------ worker thread
    def _drain(self) -> None:
        """Drop queued text (call with the lock held); idle again if nothing is playing."""
        import queue
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        if not self._busy:
            self._idle.set()

    def _current(self, gen: int) -> bool:
        return gen == self._gen

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            gen, text = item
            with self._lock:
                self._busy = True
            self._played = False
            try:
                if self._current(gen):
                    self._speak(gen, text)
            except Exception as e:
                self.last_error = e
                if self._current(gen) and not self._played:   # don't repeat half a sentence
                    self._speak_fallback(gen, text)
            finally:
                with self._lock:
                    self._busy = False
                    if self._queue.empty():
                        self._idle.set()

    def _speak(self, gen: int, text: str) -> None:
        out = self._open_output()
        with self.client.audio.speech.with_streaming_response.create(
                model=self.model, voice=self.voice, input=text,
                instructions=self.instructions, response_format="pcm",
                timeout=self.timeout) as resp:
            pending = b""
            for chunk in resp.iter_bytes(CHUNK_BYTES):
                if not self._current(gen):
                    return                       # barge-in: drop the rest of the stream
                pending += chunk
                cut = len(pending) - len(pending) % 2   # whole int16 samples only
                if cut:
                    out.write(pending[:cut])
                    self._played = True
                    pending = pending[cut:]

    def _open_output(self):
        if self._output is None:
            import sounddevice as sd
            self._output = sd.RawOutputStream(samplerate=TTS_RATE, channels=1,
                                              dtype="int16", latency="low")
            self._output.start()
        return self._output

    def _speak_fallback(self, gen: int, text: str) -> None:
        if self._fallback is None and not self._fallback_failed:
            try:
                self._fallback = SapiSpeaker(cues=self.cues)
            except Exception:
                self._fallback_failed = True
        if self._fallback is None:
            self.cues.play("error")
            return
        # SAPI lives in this thread's COM apartment: drive it from here, and poll the
        # generation so a barge-in on the main thread still silences it.
        self._fallback.say(text)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if not self._current(gen):
                self._fallback.stop()
                return
            if self._fallback_done():
                return
            time.sleep(0.05)
        self._fallback.stop()

    def _fallback_done(self) -> bool:
        done = getattr(self._fallback, "done", None)
        if callable(done):
            return done()
        return self._fallback.voice.WaitUntilDone(0)


def create_speaker():
    """ACCEX_TTS=openai -> streamed OpenAI voice, otherwise (default) SAPI."""
    if os.getenv("ACCEX_TTS", "sapi").strip().lower() == "openai":
        return OpenAISpeaker()
    return SapiSpeaker()
