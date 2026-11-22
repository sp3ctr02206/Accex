"""ACCEX_PROFILE handling in main.py (owner: P2)."""
from __future__ import annotations

from types import SimpleNamespace

from main import SENIOR_SETTINGS, apply_profile, share_vocabulary
from mocks.demo import PrintLog


def test_default_profile_changes_nothing():
    for env in ({}, {"ACCEX_PROFILE": "default"}, {"ACCEX_PROFILE": "something-else"}):
        before = dict(env)
        assert apply_profile(env) == "default"
        assert env == before


def test_senior_profile_sets_voice_knobs_with_defaults():
    env = {"ACCEX_PROFILE": "senior", "ACCEX_ELEVEN_SPEED": "1.0"}
    assert apply_profile(env) == "senior"
    assert env["ACCEX_ELEVEN_SPEED"] == "0.85"
    assert env["ACCEX_TTS_RATE"] == "-2"
    assert env["ACCEX_STT_MIN_RMS"] == "30"


def test_senior_profile_respects_senior_overrides():
    env = {"ACCEX_PROFILE": "senior", "ACCEX_SENIOR_ELEVEN_SPEED": "0.75"}
    apply_profile(env)
    assert env["ACCEX_ELEVEN_SPEED"] == "0.75"
    assert set(SENIOR_SETTINGS) == {"ACCEX_SENIOR_ELEVEN_SPEED", "ACCEX_SENIOR_TTS_RATE",
                                    "ACCEX_SENIOR_STT_MIN_RMS"}


def _assistant(stt, words):
    senior = SimpleNamespace(vocabulary=lambda: words) if words is not None else None
    return SimpleNamespace(brain=SimpleNamespace(senior=senior), stt=stt, log=PrintLog(quiet=True))


def test_vocabulary_goes_to_stt_hook_when_available():
    got = []
    stt = SimpleNamespace(set_vocabulary=got.extend)
    assert share_vocabulary(_assistant(stt, ["Lucas", "Dr. Patel"])) == 2
    assert got == ["Lucas", "Dr. Patel"]


def test_vocabulary_is_skipped_without_hook_or_senior():
    assert share_vocabulary(_assistant(SimpleNamespace(), ["Lucas"])) == 0
    assert share_vocabulary(_assistant(SimpleNamespace(set_vocabulary=print), None)) == 0


def test_vocabulary_hook_errors_are_logged_not_raised():
    def boom(words):
        raise RuntimeError("no")
    a = _assistant(SimpleNamespace(set_vocabulary=boom), ["Lucas"])
    assert share_vocabulary(a) == 0
    assert a.log.events[-1][0] == "error"
