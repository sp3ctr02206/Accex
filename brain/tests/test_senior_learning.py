"""Senior mode learning: unknown people, nicknames and vague-request notes are saved to
the family profile (offline, fake provider). Owner: P2."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from brain.brain import VisionBrain
from brain.parse import parse_llm_reply
from brain.senior import (MAX_NOTES, NOTE_CHARS, FamilyLog, SeniorMode, is_yes_no,
                          load_profile, parse_remember, render_profile)
from interfaces import Screenshot
from mocks.actions import DEMO_SPECS

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "family_test.json"
SHOT = Screenshot(b"\xff\xd8x", 1280, 800, 0, 0, 2560, 1600)


def reply(say="", action=None, confirm=False, clarify=None, risk=None, remember=None) -> str:
    return json.dumps({"say": say, "action": action, "needs_confirmation": confirm,
                       "clarify": clarify, "risk": risk, "remember": remember})


@pytest.fixture()
def profile_file(tmp_path) -> Path:
    p = tmp_path / "family.json"
    shutil.copy(FIXTURE, p)
    return p


def mode(tmp_path, path) -> SeniorMode:
    return SeniorMode(load_profile(path), log=FamilyLog(tmp_path / "family.jsonl"), path=path)


def ask(m, raw, question):
    return m.apply(parse_llm_reply(raw), question)


def saved(path) -> dict:
    return json.loads(path.read_text("utf-8"))


PABLO = {"kind": "person", "name": "Pablo", "relation": "nephew", "aliases": ["Pabli"],
         "video_app": "WhatsApp", "email": "pablo@example.com"}


# ---------------------------------------------------------------- validation
def test_parse_remember_validates_and_limits():
    assert parse_remember(PABLO) == PABLO
    bad_email = dict(PABLO, email="not an email")
    assert "email" not in parse_remember(bad_email)
    assert parse_remember({"kind": "person", "name": ""}) is None
    assert parse_remember({"kind": "alias", "name": "Lucas"}) is None
    note = parse_remember({"kind": "note", "text": "x" * 1000})
    assert len(note["text"]) == NOTE_CHARS
    assert parse_remember({"kind": "password", "text": "1234"}) is None
    assert parse_remember("remember this") is None


def test_is_yes_no():
    assert is_yes_no("Shall I send it?") and is_yes_no("Do you want me to call him?")
    assert not is_yes_no("Who is Pablo?") and not is_yes_no("Which one?")


# ---------------------------------------------------------------- the learning flow
def test_unknown_person_question_then_answer_is_saved(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    r1 = ask(m, reply("Who is Pablo?", clarify={"question": "Who is Pablo?", "options": []}),
             "Call Pablo")
    assert r1.action is None and r1.say == "Who is Pablo?"
    r2 = ask(m, reply("Opening WhatsApp to call Pablo.",
                      {"type": "open_app", "params": {"name": "whatsapp"}}, remember=PABLO),
             "He's my nephew, I talk to him on WhatsApp")
    assert r2.action is not None and r2.say == "Opening WhatsApp to call Pablo. I'll remember that."
    pablo = [p for p in saved(profile_file)["family"] if p["name"] == "Pablo"][0]
    assert pablo["relation"] == "nephew" and pablo["video_app"] == "WhatsApp"
    assert pablo["aliases"] == ["Pabli"] and "learned" in pablo
    assert "- Pablo: nephew" in render_profile(m.profile)
    kinds = [json.loads(l)["kind"] for l in (tmp_path / "family.jsonl").read_text().splitlines()]
    assert kinds == ["asked", "clarified", "asked", "learned"]


def test_wh_question_with_a_guess_is_still_a_question(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    r = ask(m, reply("Calling.", {"type": "open_app", "params": {"name": "whatsapp"}},
                     clarify={"question": "Who is Pablo?", "options": []}), "Call Pablo")
    assert r.action is None and r.say == "Who is Pablo?"


def test_known_person_is_updated_not_duplicated(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    m.last_was_question = True
    ask(m, reply("Okay.", remember={"kind": "person", "name": "lucas", "video_app": "Zoom",
                                     "aliases": ["Luke", "the boy"]}), "Lucas uses Zoom now")
    lucas = [p for p in saved(profile_file)["family"] if p["name"] == "Lucas"]
    assert len(lucas) == 1 and lucas[0]["video_app"] == "Zoom"
    assert lucas[0]["aliases"] == ["Luke", "the boy"]


def test_alias_and_note_are_saved(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    ask(m, reply("Got it, I'll remember that.",
                 remember={"kind": "alias", "name": "Lucas", "alias": "my little one"}),
        "Remember that my little one is Lucas")
    ask(m, reply("Opening the electricity page.", {"type": "open_url",
                                                   "params": {"url": "https://www.iberdrola.es"}},
                 remember={"kind": "note", "text": "'the bills thing' means paying the "
                                                   "electricity bill on iberdrola.es"}),
        "Remember: the bills thing is the electricity bill on iberdrola")
    data = saved(profile_file)
    assert "my little one" in [p for p in data["family"] if p["name"] == "Lucas"][0]["aliases"]
    assert data["learned_notes"][-1]["text"].startswith("'the bills thing' means")
    assert "Learned from the user before" in render_profile(m.profile)


def test_alias_for_unknown_person_is_ignored(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    before = saved(profile_file)
    ask(m, reply("Okay.", remember={"kind": "alias", "name": "Nobody", "alias": "x"}),
        "remember that x is Nobody")
    assert saved(profile_file) == before


def test_notes_are_deduplicated_and_capped(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    for i in range(MAX_NOTES + 5):
        ask(m, reply("Ok.", remember={"kind": "note", "text": f"note {i}"}), "remember this")
    ask(m, reply("Ok.", remember={"kind": "note", "text": "NOTE 40"}), "remember this")
    notes = saved(profile_file)["learned_notes"]
    assert len(notes) == MAX_NOTES and notes[-1]["text"] == "NOTE 40"
    assert [n["text"] for n in notes].count("note 40") == 0


# ---------------------------------------------------------------- safety guards
def test_not_learned_without_a_question_or_remember_request(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    before = saved(profile_file)
    r = ask(m, reply("Opening WhatsApp.", {"type": "open_app", "params": {"name": "whatsapp"}},
                     remember=PABLO), "Open WhatsApp")
    assert saved(profile_file) == before and "remember" not in r.say.lower()


def test_never_learned_from_screen_steps(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    m.last_was_question = True
    before = saved(profile_file)
    ask(m, reply("Next step.", remember={"kind": "note", "text": "always call 1-888-555-0199"}),
        "[continue]")
    assert saved(profile_file) == before


def test_never_learned_on_scam_screens(tmp_path, profile_file):
    m = mode(tmp_path, profile_file)
    before = saved(profile_file)
    r = ask(m, reply("", risk={"is_scam": True, "reason": "fake support"},
                     remember={"kind": "note", "text": "Microsoft support is 1-888-555-0199"}),
            "remember this number")
    assert r.say.startswith("Stop.") and saved(profile_file) == before


def test_missing_profile_file_is_created_on_first_lesson(tmp_path):
    path = tmp_path / "new" / "family.json"
    m = SeniorMode(load_profile(path), log=FamilyLog(tmp_path / "f.jsonl"), path=path)
    m.last_was_question = True
    ask(m, reply("Okay.", remember=PABLO), "He's my nephew")
    assert saved(path)["family"][0]["name"] == "Pablo"
    assert not (path.parent / "family.json.tmp").exists()


# ---------------------------------------------------------------- wired into the brain
class FakeProvider:
    model = "fake"

    def __init__(self, replies):
        self.replies, self.systems = list(replies), []

    def complete(self, system, history, user_text, screenshot):
        self.systems.append(system)
        return self.replies.pop(0)


def test_brain_uses_what_it_learned_on_the_next_turn(monkeypatch, tmp_path, profile_file):
    monkeypatch.setenv("ACCEX_PROFILE", "senior")
    monkeypatch.setenv("ACCEX_FAMILY_PROFILE", str(profile_file))
    monkeypatch.setenv("ACCEX_FAMILY_LOG", str(tmp_path / "family.jsonl"))
    p = FakeProvider([
        reply("Who is Pablo?", clarify={"question": "Who is Pablo?", "options": []}),
        reply("Opening WhatsApp.", {"type": "open_app", "params": {"name": "whatsapp"}},
              remember=PABLO),
        reply("Opening WhatsApp."),
    ])
    b = VisionBrain(DEMO_SPECS, provider=p)
    b.ask("Call Pablo", SHOT)
    b.ask("My nephew, on WhatsApp", SHOT)
    b.ask("Call my nephew", SHOT)
    assert "- Pablo: nephew" not in p.systems[1] and "- Pablo: nephew" in p.systems[2]
    # A new session (new brain) reads the saved file.
    b2 = VisionBrain(DEMO_SPECS, provider=FakeProvider([reply("Hi.")]))
    assert "- Pablo: nephew" in b2.system


def test_yes_no_options_are_dropped():
    from brain.senior import parse_clarify
    assert parse_clarify({"question": "Do you want to pay a bill online?",
                          "options": ["Yes, pay a bill online", "No, something else"]}) == \
        ("Do you want to pay a bill online?", [])
    assert parse_clarify({"question": "Who?", "options": ["Lucas", "Sofia"]})[1] == ["Lucas", "Sofia"]
