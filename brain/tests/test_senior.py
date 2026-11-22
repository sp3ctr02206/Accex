"""Senior mode, offline (fake provider, no API). Owner: P2."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain import senior
from brain.senior import (MORE_DETAIL, FamilyLog, SeniorMode, format_question, load_profile,
                          parse_clarify, parse_risk, prompt_block, render_profile, vocabulary)
from interfaces import Action, ActionResult
from brain.parse import parse_llm_reply

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "family_test.json"


def reply(say="", action=None, confirm=False, clarify=None, risk=None) -> str:
    return json.dumps({"say": say, "action": action, "needs_confirmation": confirm,
                       "clarify": clarify, "risk": risk})


def mode(tmp_path, profile=None) -> SeniorMode:
    return SeniorMode(profile, log=FamilyLog(tmp_path / "family.jsonl"))


def events(tmp_path) -> list[dict]:
    p = tmp_path / "family.jsonl"
    return [json.loads(l) for l in p.read_text("utf-8").splitlines()] if p.exists() else []


# ---------------------------------------------------------------- profile (case e)
def test_missing_profile_is_none(tmp_path):
    assert load_profile(tmp_path / "nope.json") is None


@pytest.mark.parametrize("content", ["{broken", "[1, 2]", ""])
def test_broken_profile_is_none(tmp_path, content):
    p = tmp_path / "family.json"
    p.write_text(content, encoding="utf-8")
    assert load_profile(p) is None


def test_no_profile_still_builds_prompt_and_vocabulary():
    block = prompt_block(None)
    assert "No family profile is available" in block and "SENIOR MODE" in block
    assert vocabulary(None) == []


def test_profile_rendering_and_vocabulary():
    profile = load_profile(FIXTURE)
    text = render_profile(profile)
    assert "- Lucas: grandson; also called Luke; video calls on WhatsApp" in text
    assert "Patient portal (\"the doctor thing\"): https://portal.riversideclinic.example.com" in text
    assert len(text) <= senior.PROFILE_CHARS
    assert vocabulary(profile)[:3] == ["Lucas", "Luke", "Sofia"]


def test_profile_text_is_capped_and_single_line_fields():
    profile = {"family": [{"name": "N" * 500, "relation": "x\ny"}] * 50}
    text = render_profile(profile)
    assert len(text) <= senior.PROFILE_CHARS and "x y" in text


def test_prompt_block_is_valid_format_and_mentions_fields():
    block = prompt_block(load_profile(FIXTURE))
    assert '"clarify": null or {"question"' in block and '"risk": null or {"is_scam"' in block


# ---------------------------------------------------------------- helpers
def test_parse_clarify_caps_options():
    assert parse_clarify({"question": "Who?", "options": ["A", "B", "C"]}) == ("Who?", ["A", "B"])
    assert parse_clarify({"question": " ", "options": ["A"]}) is None
    assert parse_clarify("Who?") is None


def test_format_question():
    assert format_question("Who do you want to call", ["Lucas", "Sofia"]) == \
        "Who do you want to call? Lucas, or Sofia?"
    assert format_question("Which one?", []) == "Which one?"


def test_parse_risk():
    assert parse_risk({"is_scam": True, "reason": "Fake virus warning."}) == "fake virus warning"
    assert parse_risk({"is_scam": "true"}) == senior.FALLBACK_REASON
    assert parse_risk({"is_scam": False, "reason": "x"}) is None
    assert parse_risk(None) is None


# ---------------------------------------------------------------- apply()
def apply(m, raw, question="hello"):
    return m.apply(parse_llm_reply(raw), question)


def test_clear_reply_passes_through_unchanged(tmp_path):
    raw = reply("Opening YouTube.", {"type": "open_url", "params": {"url": "https://youtube.com"}})
    resp = parse_llm_reply(raw)
    assert mode(tmp_path).apply(resp, "Open YouTube") is resp


def test_scam_blocks_action_and_is_logged(tmp_path):
    m = mode(tmp_path)
    r = apply(m, reply("Calling the number.", {"type": "press_key", "params": {"keys": "enter"}},
                       risk={"is_scam": True, "reason": "Fake Microsoft virus warning"}),
              "Call that number")
    assert r.action is None and r.needs_confirmation is False
    assert r.say == ("Stop. This looks like a scam: fake Microsoft virus warning. "
                     "Don't click, call or pay anything.")
    kinds = [e["kind"] for e in events(tmp_path)]
    assert kinds == ["asked", "blocked"]


def test_scam_during_task_is_logged_without_fake_question(tmp_path):
    m = mode(tmp_path)
    apply(m, reply("", risk={"is_scam": True, "reason": "gift card request"}), "[continue]")
    assert [e["kind"] for e in events(tmp_path)] == ["blocked"]
    assert events(tmp_path)[0]["text"] == "(screen during a task)"


def test_clarify_asks_once_with_no_action(tmp_path):
    m = mode(tmp_path)
    r = apply(m, reply("Calling Lucas.", {"type": "open_app", "params": {"name": "whatsapp"}},
                       clarify={"question": "Who do you want to call?",
                                "options": ["Lucas", "Sofia", "Ana"]}), "Call the kids")
    assert r.action is None and r.say == "Who do you want to call? Lucas, or Sofia?"
    assert [e["kind"] for e in events(tmp_path)] == ["asked", "clarified"]


def test_second_question_in_a_row_runs_best_guess(tmp_path):
    m = mode(tmp_path)
    q = {"question": "Who?", "options": ["Lucas", "Sofia"]}
    apply(m, reply("Who?", {"type": "open_app", "params": {"name": "whatsapp"}}, clarify=q))
    r = apply(m, reply("Who exactly?", {"type": "open_app", "params": {"name": "whatsapp"}},
                       clarify=q), "the boy")
    assert r.action == Action("open_app", {"name": "whatsapp"})
    assert r.say == "I'll try my best guess."


def test_second_question_without_guess_asks_for_detail_once(tmp_path):
    m = mode(tmp_path)
    q = {"question": "Which?", "options": []}
    apply(m, reply("Which?", clarify=q))
    r = apply(m, reply("Which?", clarify=q))
    assert r.action is None and r.say == MORE_DETAIL
    r3 = apply(m, reply("Which one?", clarify=q))      # counter reset: may ask again later
    assert r3.say == "Which?"


def test_question_flag_resets_after_normal_reply(tmp_path):
    m = mode(tmp_path)
    q = {"question": "Who?", "options": ["A", "B"]}
    apply(m, reply("Who?", clarify=q))
    apply(m, reply("Okay."))
    assert apply(m, reply("Who?", clarify=q)).say == "Who? A, or B?"


def test_actions_are_logged_text_only(tmp_path):
    m = mode(tmp_path)
    m.on_action(Action("open_url", {"url": "x"}), ActionResult(True, "Opening x."))
    m.on_action(Action("click", {"x": 1, "y": 2}), ActionResult(False, "Missed."))
    ev = events(tmp_path)
    assert [(e["kind"], e["text"], e["detail"]) for e in ev] == \
        [("done", "open_url", "Opening x."), ("failed", "click", "Missed.")]
    assert set(ev[0]) == {"t", "kind", "text", "detail"}


def test_family_log_never_raises(tmp_path):
    FamilyLog(tmp_path / "a_dir_not_a_file" / "x" / "\0bad").write("asked", "hi")


def test_enabled_flag():
    assert senior.enabled({"ACCEX_PROFILE": "senior"})
    assert senior.enabled({"ACCEX_PROFILE": " Senior "})
    assert not senior.enabled({})
    assert not senior.enabled({"ACCEX_PROFILE": "default"})
