"""Voice unit tests: no microphone, no keyboard hook, no API key."""
import io
import threading
import wave

import numpy as np
import pytest

from interfaces import AccexError, AudioClip
from voice.cues import PATTERNS, make_cue
from voice.hotkey import SAMPLE_RATE, PushToTalkListener, build_wav, is_tap
from voice.stt import OpenAISTT, clip_rms


def pcm(seconds, amp=3000):
    n = int(SAMPLE_RATE * seconds)
    t = np.arange(n) / SAMPLE_RATE
    return (np.sin(2 * np.pi * 440 * t) * amp).astype(np.int16).tobytes()


# ------------------------------------------------------------ WAV builder
def test_build_wav_format():
    data = pcm(0.5)
    with wave.open(io.BytesIO(build_wav(data)), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.readframes(w.getnframes()) == data


def test_is_tap():
    assert is_tap(0.1) and is_tap(0.29)
    assert not is_tap(0.3) and not is_tap(2.0)


# ------------------------------------------------------------ listener (no hardware)
def feed(lst, data):
    lst._on_audio(data, len(data) // 2, None, None)


def test_utterance_returned_and_on_start_called():
    lst = PushToTalkListener(start=False)
    calls = []
    lst.key_down(t=0.0)
    feed(lst, pcm(1.0))
    lst.key_down(t=0.1)            # key auto-repeat: ignored
    lst.key_up(t=1.0)
    clip = lst.wait_for_utterance(lambda: calls.append("start"))
    assert calls == ["start"]
    assert clip.duration_s == pytest.approx(1.0, abs=0.01)
    with wave.open(io.BytesIO(clip.wav_bytes)) as w:
        assert w.getframerate() == 16000


def test_tap_silences_but_is_not_returned():
    lst = PushToTalkListener(start=False)
    calls = []
    lst.key_down(t=0.0); feed(lst, pcm(0.1)); lst.key_up(t=0.1)     # tap
    lst.key_down(t=1.0); feed(lst, pcm(0.8)); lst.key_up(t=1.8)     # real
    clip = lst.wait_for_utterance(lambda: calls.append("start"))
    assert calls == ["start", "start"]
    assert clip.duration_s > 0.5


def test_audio_outside_key_press_is_dropped_except_preroll():
    lst = PushToTalkListener(start=False)
    for _ in range(20):            # 0.2 s before key down: only ~0.15 s pre-roll kept
        feed(lst, pcm(0.01))
    lst.key_down(t=0.0)
    feed(lst, pcm(0.5))
    lst.key_up(t=0.5)
    clip = lst.wait_for_utterance()
    assert 0.6 <= clip.duration_s <= 0.67


def test_events_from_another_thread():
    lst = PushToTalkListener(start=False)

    def press():
        lst.key_down(t=0.0); feed(lst, pcm(0.6)); lst.key_up(t=0.6)

    threading.Timer(0.05, press).start()
    assert lst.wait_for_utterance().duration_s > 0.5


# ------------------------------------------------------------ cues
def test_cues_distinct_and_short():
    cues = {name: make_cue(name) for name in PATTERNS}
    assert set(cues) == {"listening", "thinking", "done", "error"}
    for samples in cues.values():
        assert samples.dtype == np.float32
        assert 0 < len(samples) / 44100 < 0.5
        assert np.abs(samples).max() <= 1.0
    assert len({s.tobytes() for s in cues.values()}) == 4


# ------------------------------------------------------------ STT (fake client)
class FakeTranscriptions:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return type("R", (), {"text": r})()


def fake_client(replies):
    tr = FakeTranscriptions(replies)
    client = type("C", (), {})()
    client.audio = type("A", (), {"transcriptions": tr})()
    return client, tr


def clip(seconds=1.0, amp=3000):
    data = pcm(seconds, amp)
    return AudioClip(build_wav(data), seconds)


def test_stt_sends_in_memory_wav_in_english():
    client, tr = fake_client(["  What's on my screen? "])
    assert OpenAISTT(model="m", client=client).transcribe(clip()) == "What's on my screen?"
    call = tr.calls[0]
    assert call["language"] == "en" and call["model"] == "m"
    assert call["file"][0] == "speech.wav" and call["file"][1][:4] == b"RIFF"


def test_stt_silence_skips_api():
    client, tr = fake_client([])
    assert OpenAISTT(client=client).transcribe(clip(amp=0)) == ""
    assert tr.calls == []
    assert clip_rms(clip(amp=0)) == 0.0


def _bare(cls, **attrs):
    """openai exception instance without building an HTTP request/response."""
    e = cls.__new__(cls)
    e.__dict__.update(attrs)
    return e


def _status_error(code):
    import openai
    return _bare(openai.APIStatusError, status_code=code)


def test_stt_falls_back_to_whisper():
    client, tr = fake_client([_status_error(404), "hello"])
    assert OpenAISTT(model="gpt-4o-mini-transcribe", client=client).transcribe(clip()) == "hello"
    assert [c["model"] for c in tr.calls] == ["gpt-4o-mini-transcribe", "whisper-1"]


def test_stt_errors_are_speakable():
    import openai
    err = _bare(openai.APIConnectionError)
    client, _ = fake_client([err])
    with pytest.raises(AccexError) as e:
        OpenAISTT(client=client).transcribe(clip())
    assert e.value.spoken == "I can't reach the internet right now."


def test_stt_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AccexError):
        OpenAISTT()
