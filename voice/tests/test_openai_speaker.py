"""OpenAISpeaker tests: fake HTTP stream, fake audio output, fake SAPI fallback."""
import time

import pytest

from interfaces import AccexError
from voice.tts import OpenAISpeaker


class FakeStream:
    def __init__(self, chunks, delay=0.0, fail_after=None):
        self.chunks, self.delay, self.fail_after = chunks, delay, fail_after

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self, size):
        for i, c in enumerate(self.chunks):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("network dropped")
            time.sleep(self.delay)
            yield c


class FakeClient:
    def __init__(self, make_stream):
        self.calls = []
        outer = self

        class SR:
            def create(self, **kw):
                outer.calls.append(kw)
                return make_stream(kw)

        self.audio = type("A", (), {})()
        self.audio.speech = type("S", (), {})()
        self.audio.speech.with_streaming_response = SR()


class FakeOut:
    def __init__(self):
        self.data = bytearray()

    def write(self, b):
        self.data += b


class FakeSapi:
    def __init__(self):
        self.said, self.stopped = [], 0

    def say(self, text):
        self.said.append(text)

    def stop(self):
        self.stopped += 1

    def done(self):
        return True


class SilentCues:
    def play(self, name):
        pass


def speaker(make_stream, fallback=None):
    out = FakeOut()
    sp = OpenAISpeaker(client=FakeClient(make_stream), output=out, cues=SilentCues(),
                       fallback=fallback or FakeSapi())
    return sp, out


def test_say_streams_pcm_and_returns_immediately():
    sp, out = speaker(lambda kw: FakeStream([b"\x01\x02" * 10, b"\x03"] + [b"\x04"], delay=0.02))
    t0 = time.perf_counter()
    sp.say("Hello there")
    assert time.perf_counter() - t0 < 0.02          # non-blocking
    sp.wait(2)
    assert bytes(out.data) == b"\x01\x02" * 10 + b"\x03\x04"   # odd byte held until paired
    kw = sp.client.calls[0]
    assert kw["input"] == "Hello there" and kw["response_format"] == "pcm"


def test_stop_interrupts_stream():
    sp, out = speaker(lambda kw: FakeStream([b"\x00\x00" * 100] * 100, delay=0.01))
    sp.say("A long answer")
    time.sleep(0.1)
    sp.stop()
    sp.wait(1)
    written = len(out.data)
    time.sleep(0.1)
    assert len(out.data) == written < 200 * 100


def test_new_say_replaces_old():
    sp, out = speaker(lambda kw: FakeStream([kw["input"][:1].encode() * 2] * 20, delay=0.01))
    sp.say("aaaa")
    time.sleep(0.05)
    sp.say("bbbb")
    sp.wait(2)
    assert out.data.endswith(b"bb") and b"a" in out.data
    assert [c["input"] for c in sp.client.calls] == ["aaaa", "bbbb"]


def test_api_failure_falls_back_to_sapi():
    fb = FakeSapi()
    sp, out = speaker(lambda kw: FakeStream([b"\x00\x00"], fail_after=0), fallback=fb)
    sp.say("Your email was sent.")
    sp.wait(2)
    assert fb.said == ["Your email was sent."] and sp.last_error is not None


def test_failure_mid_sentence_does_not_repeat():
    fb = FakeSapi()
    sp, out = speaker(lambda kw: FakeStream([b"\x00\x00"] * 5, fail_after=2), fallback=fb)
    sp.say("Half")
    sp.wait(2)
    assert fb.said == [] and len(out.data) == 4


def test_wait_does_not_hang_after_stop_and_empty_say():
    sp, _ = speaker(lambda kw: FakeStream([]))
    sp.stop()
    sp.say("")
    t0 = time.perf_counter()
    sp.wait(1)
    assert time.perf_counter() - t0 < 0.5


def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AccexError):
        OpenAISpeaker()


def test_factory_picks_engine(monkeypatch):
    import voice.tts as tts
    monkeypatch.setattr(tts, "SapiSpeaker", lambda: "sapi")
    monkeypatch.setattr(tts, "OpenAISpeaker", lambda: "openai")
    monkeypatch.setenv("ACCEX_TTS", "openai")
    assert tts.create_speaker() == "openai"
    monkeypatch.setenv("ACCEX_TTS", "sapi")
    assert tts.create_speaker() == "sapi"
