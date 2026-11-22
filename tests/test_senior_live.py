"""Live senior-mode eval against the real model (owner: P2).

Skipped by default (costs API calls). Run with:
    ACCEX_LIVE_TESTS=1 pytest tests/test_senior_live.py -s
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("ACCEX_LIVE_TESTS") != "1",
                                reason="live API eval; set ACCEX_LIVE_TESTS=1")


@pytest.fixture(scope="module")
def results():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    from brain.eval_senior import run
    saved = {k: os.environ.get(k) for k in ("ACCEX_PROFILE", "ACCEX_FAMILY_PROFILE",
                                            "ACCEX_FAMILY_LOG")}
    try:
        yield run()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_vague_requests(results):            # (b)
    assert results["vague"][0] >= 18


def test_clear_requests_never_clarified(results):   # (c)
    assert results["clear"]["questions"] == 0
    # Same request must succeed in both profiles. The exact action may legitimately vary
    # (e.g. "Go back" = alt+left or clicking the back arrow), so type equality is reported only.
    ok, total = results["clear"]["ok"]
    assert ok == total


def test_scams_flagged_and_normal_pages_not(results):   # (d)
    assert results["scam"]["flagged"][0] == results["scam"]["flagged"][1]
    assert results["scam"]["false_positives"][0] == 0


def test_senior_latency_budget(results):
    assert results["clear"]["p50_senior"] - results["clear"]["p50_default"] <= 150
