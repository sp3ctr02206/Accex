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


def make(lines, brain=None, slow_notice_s=1.5, listener=None, executor=None, max_steps=10):
    executor = executor or LoggingExecutor(quiet=True)
    a = Assistant(listener=listener or ScriptedListener(lines), stt=ConsoleSTT(),
                  speaker=PrintSpeaker(quiet=True), capturer=StaticCapturer(),
                  brain=brain or ScriptedBrain(executor.specs()), executor=executor,
                  gate=KeywordGate(), log=PrintLog(quiet=True), slow_notice_s=slow_notice_s,
                  max_steps=max_steps, settle_scale=0)
    return a, a.speaker, executor


def task_ends(a):
    return [d for e, d in a.log.events if e == "task_end"]


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


# ---------------------------------------------------------------- multi-step tasks
from interfaces import Action, ActionResult  # noqa: E402


class ListBrain(ScriptedBrain):
    """Returns the given replies in order, whatever the question."""

    def __init__(self, replies):
        super().__init__([])
        self.replies = list(replies)
        self.questions = []

    def ask(self, question, screenshot):
        self.questions.append(question)
        return self.replies.pop(0) if self.replies else LLMResponse(say="Done.")


def test_multi_step_task_runs_to_the_end_without_asking():
    a, speaker, executor = make(["Play Money for Nothing on Spotify"])
    a.run_turn()
    assert [x.type for x in executor.executed] == ["open_app", "click", "type_text", "press_key"]
    assert speaker.said == ["Opening Spotify.", "Clicking search.", "Typing the song.",
                            "Searching.", "Money for Nothing by Dire Straits is playing."]
    assert task_ends(a)[-1]["reason"] == "done" and task_ends(a)[-1]["steps"] == 4


def test_result_is_described_after_looking_again():
    brain = ListBrain([LLMResponse(say="Opening Gmail.",
                                   action=Action("open_url", {"url": "https://mail.google.com"})),
                       LLMResponse(say="Gmail is open with 3 unread emails.")])
    a, speaker, _ = make(["Open my mail"], brain=brain)
    a.run_turn()
    assert brain.questions == ["Open my mail", "[continue]"]
    assert speaker.said == ["Opening Gmail.", "Gmail is open with 3 unread emails."]


def test_max_steps_stops_the_task():
    a, speaker, executor = make(["Play Money for Nothing on Spotify"], max_steps=2)
    a.run_turn()
    assert len(executor.executed) == 2
    assert speaker.said[-1] == "I've done 2 steps and stopped. Say continue to keep going."
    assert task_ends(a)[-1]["reason"] == "max_steps"


class InterruptingListener(ScriptedListener):
    def __init__(self, lines, executor, after):
        super().__init__(lines)
        self.executor, self.after = executor, after

    def interrupted(self):
        return len(self.executor.executed) >= self.after


def test_push_to_talk_interrupts_a_running_task():
    executor = LoggingExecutor(quiet=True)
    listener = InterruptingListener(["Play Money for Nothing on Spotify"], executor, after=2)
    a, speaker, _ = make(None, listener=listener, executor=executor)
    a.run_turn()
    assert len(executor.executed) == 2
    assert task_ends(a)[-1]["reason"] == "interrupted"
    assert "playing" not in " ".join(speaker.said)


def test_dangerous_step_pauses_then_task_resumes_after_yes():
    brain = ListBrain([
        LLMResponse(say="I'll reply: thanks. Do you want me to send it?",
                    action=Action("email_reply", {"body": "Thanks"}), needs_confirmation=True),
        LLMResponse(say="Archiving it.", action=Action("press_key", {"keys": "e"})),
        LLMResponse(say="Replied and archived."),
    ])
    a, speaker, executor = make(["Reply thanks and archive it", "yes"], brain=brain)
    a.run_turn()
    assert executor.executed == [] and a.pending is not None
    a.run_turn()
    assert [x.type for x in executor.executed] == ["email_reply", "press_key"]
    assert speaker.said[-1] == "Replied and archived."
    assert task_ends(a)[-1]["reason"] == "done"


class FailingExecutor(LoggingExecutor):
    def execute(self, action, screenshot):
        self.executed.append(action)
        return ActionResult(False, "I couldn't click that.")


def test_two_failures_in_a_row_stop_the_task():
    brain = ListBrain([LLMResponse(say="Clicking.", action=Action("click", {"x": 1, "y": 1}))
                       for _ in range(5)])
    a, speaker, executor = make(["click it"], brain=brain, executor=FailingExecutor(quiet=True))
    a.run_turn()
    assert len(executor.executed) == 2
    assert speaker.said[-1] == "I couldn't finish this task."
    assert task_ends(a)[-1]["reason"] == "failed"


def test_repeating_the_same_action_is_stopped():
    brain = ListBrain([LLMResponse(say="Scrolling.",
                                   action=Action("scroll", {"direction": "down"}))
                       for _ in range(10)])
    a, speaker, executor = make(["scroll to the bottom"], brain=brain)
    a.run_turn()
    assert len(executor.executed) == 3
    assert "stuck" in speaker.said[-1]
