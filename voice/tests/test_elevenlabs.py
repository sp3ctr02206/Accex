import io
import json
import time
import urllib.error

import pytest

from interfaces import AccexError
from voice.elevenlabs import ElevenLabsSpeaker


class FakeOutput:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


class FakeCues:
    def __init__(self):
        self.played = []

    def play(self, name):
        self.played.append(name)


class FakeFallback:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)

    def stop(self):
        pass

    def done(self):
        return True


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def make(opener, **kw):
    return ElevenLabsSpeaker(api_key="test-key", voice_id="VOICE", model="eleven_flash_v2_5",
                             cues=FakeCues(), output=FakeOutput(), fallback=FakeFallback(),
                             opener=opener, **kw)


def test_request_shape():
    sp = make(lambda req, timeout: None)
    req = sp.request("Hello.")
    assert req.full_url == ("https://api.elevenlabs.io/v1/text-to-speech/VOICE/stream"
                            "?output_format=pcm_24000")
    assert req.get_method() == "POST"
    assert req.get_header("Xi-api-key") == "test-key"
    body = json.loads(req.data)
    assert body["text"] == "Hello." and body["model_id"] == "eleven_flash_v2_5"


def test_streams_pcm_to_output():
    audio = bytes(range(256)) * 40 + b"\x01"          # odd length: last byte dropped
    seen = []

    def opener(req, timeout):
        seen.append(req)
        return FakeResponse(audio)

    sp = make(opener)
    sp.say("Hi there.")
    sp.wait(2)
    assert sp._output.data == audio[:-1]
    assert sp._fallback.said == [] and len(seen) == 1


def test_http_error_falls_back_to_sapi():
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    sp = make(opener)
    sp.say("Fallback please.")
    sp.wait(2)
    assert sp._fallback.said == ["Fallback please."]
    assert isinstance(sp.last_error, urllib.error.HTTPError)


def test_barge_in_drops_rest_of_stream():
    class SlowResponse(FakeResponse):
        def read(self, n=-1):
            time.sleep(0.02)
            return super().read(n)

    sp = make(lambda req, timeout: SlowResponse(b"\x00\x01" * 24000))   # ~1 s of audio
    sp.say("A long sentence.")
    time.sleep(0.08)
    sp.stop()
    sp.wait(2)
    assert 0 < len(sp._output.data) < 48000


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(AccexError):
        ElevenLabsSpeaker()
