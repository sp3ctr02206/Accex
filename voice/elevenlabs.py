"""ElevenLabs voice (ACCEX_TTS=elevenlabs). Implements interfaces.Speaker.

Streams POST /v1/text-to-speech/{voice_id}/stream as raw 24 kHz 16-bit PCM and plays it
while it downloads. Reuses OpenAISpeaker's worker thread, so say()/stop() return at once,
a push-to-talk press cuts speech within ~50 ms, and any API error falls back to the
Windows SAPI voice so the user always hears the answer. Standard library HTTP only.

    python -m voice.elevenlabs --voices          # list voices available to your key
    python -m voice.elevenlabs "Hello, I'm Accex."   # speak a sample with the current voice
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from interfaces import AccexError

from .cues import CuePlayer
from .tts import CHUNK_BYTES, TTS_RATE, OpenAISpeaker

API = "https://api.elevenlabs.io"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"        # premade voice used in the ElevenLabs docs
DEFAULT_MODEL = "eleven_flash_v2_5"           # ~100 ms latency per the ElevenLabs docs
OUTPUT_FORMAT = f"pcm_{TTS_RATE}"             # same 24 kHz stream OpenAISpeaker plays


class ElevenLabsSpeaker(OpenAISpeaker):
    def __init__(self, api_key: str | None = None, voice_id: str | None = None,
                 model: str | None = None, cues: CuePlayer | None = None,
                 output=None, fallback=None, opener=None) -> None:
        key = api_key or os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not key:
            raise AccexError("My voice key is missing. Please check the setup.",
                             "ELEVENLABS_API_KEY is not set")
        # client="elevenlabs" skips the OpenAI client; the worker thread is reused as is.
        super().__init__(client="elevenlabs", cues=cues, output=output, fallback=fallback)
        self.api_key = key
        self.voice = voice_id or os.getenv("ACCEX_ELEVEN_VOICE", "").strip() or DEFAULT_VOICE
        self.model = model or os.getenv("ACCEX_ELEVEN_MODEL", "").strip() or DEFAULT_MODEL
        self.speed = float(os.getenv("ACCEX_ELEVEN_SPEED", "1.0"))
        self.timeout = float(os.getenv("ACCEX_TTS_TIMEOUT", "10"))
        self._urlopen = opener or urllib.request.urlopen

    def request(self, text: str) -> urllib.request.Request:
        body = {"text": text, "model_id": self.model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
                                   "speed": self.speed}}
        return urllib.request.Request(
            f"{API}/v1/text-to-speech/{self.voice}/stream?output_format={OUTPUT_FORMAT}",
            data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json"})

    def _speak(self, gen: int, text: str) -> None:
        """Runs on the worker thread; any exception triggers the SAPI fallback."""
        out = self._open_output()
        with self._urlopen(self.request(text), timeout=self.timeout) as resp:
            pending = b""
            while True:
                chunk = resp.read(CHUNK_BYTES)
                if not chunk:
                    break
                if not self._current(gen):
                    return                              # barge-in: drop the rest
                pending += chunk
                cut = len(pending) - len(pending) % 2   # whole int16 samples only
                if cut:
                    out.write(pending[:cut])
                    self._played = True
                    pending = pending[cut:]


def list_voices(api_key: str) -> list[dict]:
    req = urllib.request.Request(f"{API}/v2/voices?page_size=100&sort=name",
                                 headers={"xi-api-key": api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp).get("voices", [])


def _main() -> int:
    import sys
    import time
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("ELEVENLABS_API_KEY is not set in .env")
        return 1
    args = sys.argv[1:]
    if args[:1] == ["--voices"]:
        try:
            voices = list_voices(key)
        except urllib.error.HTTPError as e:
            print(f"ElevenLabs error {e.code}: {e.read()[:300]!r}")
            return 1
        for v in voices:
            labels = v.get("labels") or {}
            desc = ", ".join(str(x) for x in (labels.get("gender"), labels.get("accent"),
                                              labels.get("age"), labels.get("use_case")) if x)
            print(f"{v.get('voice_id')}  {v.get('name')}  [{v.get('category')}] {desc}")
        return 0
    text = " ".join(args) or "Hello, I'm Accex. March had the highest sales, at 142 thousand dollars."
    sp = ElevenLabsSpeaker()
    print(f"voice {sp.voice}, model {sp.model}")
    t = time.perf_counter()
    sp.say(text)
    while not sp._played and sp.last_error is None and time.perf_counter() - t < 10:
        time.sleep(0.01)
    if sp.last_error:
        print(f"ElevenLabs failed ({sp.last_error!r}); speaking with Windows voice instead")
    else:
        print(f"first audio after {round((time.perf_counter() - t) * 1000)} ms")
    sp.wait(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
