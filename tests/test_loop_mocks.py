"""Full loop with all mocks (owner: P2). Runs with only pytest installed."""
from __future__ import annotations

import time

from interfaces import AccexError, LLMResponse, Screenshot
from main import Assistant
from mocks.actions import KeywordGate, LoggingExecutor
from mocks.brain import ScriptedBrain, StaticCapturer
from mocks.demo import PrintLog
from mocks.voice import ConsoleSTT, PrintSpeaker, ScriptedListener

DEMO = ["What's on my screen?", "Which month had the highest sales?", "And the lowest?",
        "Read me my latest email.", "Reply that I'll review it tomorrow."]


def make(lines, brain=None, slow_notice_s=1.5):
    executor = LoggingExecutor(quiet=True)
    a = Assistant(listener=ScriptedListener(lines), stt=ConsoleSTT(),
                  speaker=PrintSpeaker(quiet=True), capturer=StaticCapturer(),
                  brain=brain or ScriptedBrain(executor.specs()), executor=executor,
                  gate=KeywordGate(), log=PrintLog(quiet=True), slow_notice_s=slow_notice_s)
    return a, a.speaker, executor


def run_all(a, n):
    for _ in range(n):
        a.run_turn()


def test_demo_script_sends_only_after_yes():
    a, speaker, executor = make(DEMO + ["Yes."])
    run_all(a, len(DEMO))
    said = " ".join(speaker.said)
    assert "dashboard" in said and "March" in said and "August" in said and "Maria" in said
    assert speaker.said[-1].endswith("Do you want me to send it?")
    assert executor.executed == []          # nothing sent before confirmation
    a.run_turn()                            # "Yes."
    assert [x.type for x in executor.executed] == ["email_reply"]
    assert speaker.said[-1] == "Email sent."
    assert a.pending is None


def test_no_cancels():
    a, speaker, executor = make(DEMO[-1:] + ["No, don't send it."])
    run_all(a, 2)
    assert executor.executed == []
    assert speaker.said[-1] == "Okay, cancelled."
    assert a.pending is None


def test_unclear_reasks_then_yes():
    a, speaker, executor = make(DEMO[-1:] + ["maybe", "yes"])
    run_all(a, 2)
    assert speaker.said[-1] == "Please say yes or no."
    assert a.pending is not None and executor.executed == []
    a.run_turn()
    assert len(executor.executed) == 1


def test_empty_transcript():
    a, speaker, _ = make(["   "])
    a.run_turn()
    assert speaker.said[-1] == "Sorry, I didn't catch that."


class FailingBrain(ScriptedBrain):
    def ask(self, question, screenshot):
        raise AccexError("I couldn't reach the AI service.", "simulated outage")


def test_accex_error_is_spoken():
    a, speaker, _ = make(["hello"], brain=FailingBrain([]))
    a.run_turn()
    assert speaker.said[-1] == "I couldn't reach the AI service."
    assert "error" in speaker.cues


class SlowBrain(ScriptedBrain):
    def ask(self, question, screenshot):
        time.sleep(0.2)
        return LLMResponse(say="Done thinking.")


def test_slow_brain_says_one_moment():
    a, speaker, _ = make(["hello"], brain=SlowBrain([]), slow_notice_s=0.05)
    a.run_turn()
    assert speaker.said == ["One moment.", "Done thinking."]


def test_dangerous_action_confirmed_even_if_model_forgets():
    class SneakyBrain(ScriptedBrain):
        def ask(self, question, screenshot):
            r = super().ask("reply", screenshot)
            return LLMResponse(say="Replying now.", action=r.action, needs_confirmation=False)

    a, speaker, executor = make(["reply"], brain=SneakyBrain([]))
    a.run_turn()
    assert executor.executed == [] and a.pending is not None
    assert speaker.said[-1] == "Replying now. Should I go ahead?"


def test_screenshot_to_screen():
    s = Screenshot(b"", 1280, 720, 0, 0, 1920, 1080)
    assert s.to_screen(640, 360) == (960, 540)
    s2 = Screenshot(b"", 1280, 720, -1920, 0, 1920, 1080)
    assert s2.to_screen(0, 0) == (-1920, 0)
