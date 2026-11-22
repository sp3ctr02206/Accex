"""Golden snapshots of the DEFAULT profile (owner: P2).

They were generated from the v-working code before senior mode existed, and prove that
default behaviour stays byte-for-byte identical: the system prompt, every user-text
variant, the exact payloads the provider receives over a scripted conversation, and
the parser's output.

Regenerate ONLY for an intentional default change:
    python -m brain.tests.test_default_snapshot --write
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from brain.brain import VisionBrain
from brain.parse import parse_llm_reply
from brain.prompt import build_system_prompt, build_user_text
from interfaces import Action, ActionResult, Screenshot
from mocks.actions import DEMO_SPECS

SNAP = Path(__file__).resolve().parent / "snapshots"
SHOT = Screenshot(b"\xff\xd8fake", 1280, 800, 0, 0, 2560, 1600)
NOTE = "Result of your last action open_url: done. Opening youtube.com."

PARSE_INPUTS = [
    '{"say": "Hi.", "action": null, "needs_confirmation": false}',
    '```json\n{"say": "Opening.", "action": {"type": "open_url", "params": {"url": "https://x.com"}}}\n```',
    'Sure! {"say": "It says {draft}.", "action": null} done',
    '{"say": "Sending?", "action": {"type": "email_reply", "body": "Hi"}, "needs_confirmation": "true"}',
    "Plain text answer.",
    "",
]

REPLIES = [
    {"say": "A sales dashboard.", "action": None, "needs_confirmation": False},
    {"say": "Opening YouTube.", "action": {"type": "open_url",
                                           "params": {"url": "https://www.youtube.com"}},
     "needs_confirmation": False},
    {"say": "YouTube is open.", "action": None, "needs_confirmation": False},
    {"say": "August, 61 thousand dollars.", "action": None, "needs_confirmation": False},
]


class RecordingProvider:
    model = "snapshot"

    def __init__(self):
        self.replies = [json.dumps(r) for r in REPLIES]
        self.calls = []

    def complete(self, system, history, user_text, screenshot):
        self.calls.append({"system": system, "history": [list(m) for m in history],
                           "user_text": user_text,
                           "screenshot": None if screenshot is None else
                           [screenshot.width, screenshot.height, len(screenshot.jpeg_bytes)]})
        return self.replies.pop(0)


def system_prompt() -> str:
    return build_system_prompt(DEMO_SPECS)


def user_texts() -> list[str]:
    return [build_user_text("What's on my screen?", SHOT, []),
            build_user_text("What's on my screen?", None, []),
            build_user_text("Open YouTube", SHOT, [NOTE]),
            build_user_text("Open YouTube", SHOT, [NOTE], for_history=True),
            build_user_text("[continue]", SHOT, [NOTE]),
            build_user_text("[continue]", SHOT, [NOTE], for_history=True)]


def conversation() -> list[dict]:
    provider = RecordingProvider()
    brain = VisionBrain(DEMO_SPECS, provider=provider, history_turns=12)
    out = []
    for question, shot in [("What's on my screen?", SHOT), ("Open YouTube", SHOT)]:
        r = brain.ask(question, shot)
        out.append([r.say, r.action and [r.action.type, r.action.params], r.needs_confirmation])
    brain.record_action(Action("open_url", {"url": "https://www.youtube.com"}),
                        ActionResult(True, "Opening youtube.com."))
    for question, shot in [("[continue]", SHOT), ("And the lowest?", None)]:
        r = brain.ask(question, shot)
        out.append([r.say, r.action and [r.action.type, r.action.params], r.needs_confirmation])
    return [{"calls": provider.calls}, {"responses": out}]


def parsed() -> list[list]:
    out = []
    for text in PARSE_INPUTS:
        r = parse_llm_reply(text)
        out.append([r.say, r.action and [r.action.type, r.action.params],
                    r.needs_confirmation, r.raw])
    return out


def _current() -> dict[str, str]:
    dump = lambda x: json.dumps(x, indent=1, ensure_ascii=False, sort_keys=True)  # noqa: E731
    return {"system_prompt.txt": system_prompt(),
            "user_texts.json": dump(user_texts()),
            "conversation.json": dump(conversation()),
            "parsed.json": dump(parsed())}


def _clean_env(monkeypatch):
    for var in ("ACCEX_PROFILE", "ACCEX_FAMILY_PROFILE", "ACCEX_HISTORY_TURNS"):
        monkeypatch.delenv(var, raising=False)


def test_default_system_prompt_unchanged(monkeypatch):
    _clean_env(monkeypatch)
    assert _current()["system_prompt.txt"] == (SNAP / "system_prompt.txt").read_text("utf-8")


def test_default_user_texts_unchanged(monkeypatch):
    _clean_env(monkeypatch)
    assert _current()["user_texts.json"] == (SNAP / "user_texts.json").read_text("utf-8")


def test_default_provider_payloads_unchanged(monkeypatch):
    _clean_env(monkeypatch)
    assert _current()["conversation.json"] == (SNAP / "conversation.json").read_text("utf-8")


def test_default_parser_unchanged(monkeypatch):
    _clean_env(monkeypatch)
    assert _current()["parsed.json"] == (SNAP / "parsed.json").read_text("utf-8")


def test_explicit_default_profile_is_identical(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("ACCEX_PROFILE", "default")
    assert _current()["conversation.json"] == (SNAP / "conversation.json").read_text("utf-8")


if __name__ == "__main__" and "--write" in sys.argv:
    SNAP.mkdir(exist_ok=True)
    for name, content in _current().items():
        (SNAP / name).write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {SNAP / name}")
