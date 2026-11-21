import json

import pytest

from brain.brain import VisionBrain
from interfaces import AccexError, Action, ActionResult, Screenshot
from main import Assistant
from mocks.actions import DEMO_SPECS, KeywordGate, LoggingExecutor
from mocks.brain import StaticCapturer
from mocks.demo import PrintLog
from mocks.voice import ConsoleSTT, PrintSpeaker, ScriptedListener

SHOT = Screenshot(b"\xff\xd8jpeg", 1280, 800, 0, 0, 2560, 1600)


class FakeProvider:
    model = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, history, user_text, screenshot):
        self.calls.append(dict(system=system, history=list(history),
                               user_text=user_text, screenshot=screenshot))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def say(text, action=None, confirm=False):
    return json.dumps({"say": text, "action": action, "needs_confirmation": confirm})


def test_memory_and_screenshot():
    p = FakeProvider([say("A dashboard."), say("March.")])
    b = VisionBrain(DEMO_SPECS, provider=p)
    assert b.ask("What's on my screen?", SHOT).say == "A dashboard."
    assert b.ask("Highest month?", SHOT).say == "March."
    second = p.calls[1]
    assert second["screenshot"] is SHOT
    assert second["history"][0] == ("user", "User: What's on my screen?")
    assert json.loads(second["history"][1][1])["say"] == "A dashboard."
    assert "Screenshot attached: 1280x800" in second["user_text"]
    assert p.calls[0]["system"] == second["system"]  # stable system prompt


def test_history_is_trimmed():
    p = FakeProvider([say(str(i)) for i in range(5)])
    b = VisionBrain(DEMO_SPECS, provider=p, history_turns=2)
    for i in range(5):
        b.ask(f"q{i}", None)
    assert len(p.calls[-1]["history"]) == 4          # 2 turns = 4 messages
    assert p.calls[-1]["history"][0] == ("user", "User: q2")


def test_action_result_note_goes_into_next_question_once():
    p = FakeProvider([say("ok"), say("ok"), say("ok")])
    b = VisionBrain(DEMO_SPECS, provider=p)
    b.ask("reply to it", SHOT)
    b.record_action(Action("email_reply", {"body": "x"}), ActionResult(True, "Email sent."))
    b.ask("anything else?", SHOT)
    b.ask("thanks", SHOT)
    assert "email_reply: done. Email sent." in p.calls[1]["user_text"]
    assert "Email sent" in p.calls[2]["history"][2][1]       # kept in history
    assert "Email sent" not in p.calls[2]["user_text"]       # but not repeated


def test_provider_error_propagates_and_memory_unchanged():
    p = FakeProvider([AccexError("I can't reach the internet right now.", "boom")])
    b = VisionBrain(DEMO_SPECS, provider=p)
    with pytest.raises(AccexError):
        b.ask("hello", SHOT)
    assert b.turns == []


def test_reset():
    p = FakeProvider([say("a")])
    b = VisionBrain(DEMO_SPECS, provider=p)
    b.ask("q", None)
    b.reset()
    assert b.turns == [] and b.notes == []


def test_full_loop_with_vision_brain_confirms_email():
    reply = {"type": "email_reply", "params": {"body": "Thanks, I'll review it tomorrow."}}
    p = FakeProvider([say("I'll reply: thanks. Do you want me to send it?", reply, True),
                      say("Your reply was sent."),
                      say("Nothing else is pending.")])
    executor = LoggingExecutor(quiet=True)
    speaker = PrintSpeaker(quiet=True)
    a = Assistant(listener=ScriptedListener(["Reply that I'll review it tomorrow.", "yes",
                                             "anything else?"]),
                  stt=ConsoleSTT(), speaker=speaker, capturer=StaticCapturer(),
                  brain=VisionBrain(executor.specs(), provider=p), executor=executor,
                  gate=KeywordGate(), log=PrintLog(quiet=True), settle_scale=0)
    a.run_turn()
    assert executor.executed == []
    a.run_turn()                       # "yes": send, then look again and confirm
    assert [x.type for x in executor.executed] == ["email_reply"]
    assert "Email sent." in p.calls[1]["user_text"]
    assert "Continue the user's request" in p.calls[1]["user_text"]
    assert speaker.said[-1] == "Your reply was sent."
    a.run_turn()
    assert ("user", "[Screen after your last action.]") in [
        (r, t.splitlines()[-1]) for r, t in p.calls[2]["history"]]
    assert speaker.said[-1] == "Nothing else is pending."
