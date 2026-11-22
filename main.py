"""Accex entry point and orchestration loop (owner: Person 2).

    python main.py                         # everything real
    python main.py --mock all              # everything mocked: type questions in the terminal
    python main.py --mock brain,actions    # real voice, scripted brain, logged actions
    python main.py --demo --dry-run        # verbose event log; actions only logged

Loop: push-to-talk -> STT -> (screenshot taken in parallel) -> brain -> speak -> act.
Multi-step tasks: after each action Accex waits for the screen to settle, takes a new
screenshot and asks the brain to continue (question CONTINUE), until the brain returns no
action. Dangerous actions pause for a spoken yes/no; pressing the push-to-talk key stops
a running task at once.
"""
from __future__ import annotations

import ctypes
import sys

# Must run before mss/pyautogui are imported so capture and clicks use physical pixels.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

import argparse
import importlib
import json
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field

from interfaces import (AccexError, Action, ActionExecutor, ActionResult, Brain,
                        ConfirmationGate, EventLog, LLMResponse, Listener, ScreenCapturer,
                        Screenshot, Speaker, SpeechToText)

PACKAGES = ("voice", "brain", "actions", "demo")
GENERIC_ERROR = "Something went wrong. Please try again."
KEY_NAMES = {"ctrl_r": "right control", "ctrl_l": "left control", "alt_gr": "Alt Gr",
             "alt_r": "right Alt", "alt_l": "left Alt", "shift_r": "right shift",
             "menu": "the menu key", "pause": "pause", "scroll_lock": "scroll lock"}

CONTINUE = "[continue]"          # question sent to the brain between steps of a task
# Seconds to let the screen settle after an action before looking again.
SETTLE_S = {"open_app": 3.0, "open_url": 2.5, "press_key": 1.0, "click": 0.8,
            "scroll": 0.5, "type_text": 0.4, "wait": 0.0}
DEFAULT_SETTLE_S = 0.8
MAX_FAILURES = 2                 # consecutive failed actions before giving up
MAX_REPEATS = 4                  # identical actions in a row before calling it stuck
SPEECH_WAIT_S = 8.0              # longest wait for narration to finish before the next line


def hotkey_name() -> str:
    key = os.getenv("ACCEX_HOTKEY", "ctrl_r").strip().lower()
    return KEY_NAMES.get(key, key.upper() if key.startswith("f") else key)


def _ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


@dataclass
class Task:
    """Progress of one spoken request across its steps."""
    steps: int = 0
    failures: int = 0
    last: tuple | None = None
    repeats: int = 0
    t0: float = field(default_factory=time.perf_counter)


class Interrupted(Exception):
    """The user pressed the push-to-talk key while a task was running."""


class Assistant:
    def __init__(self, listener: Listener, stt: SpeechToText, speaker: Speaker,
                 capturer: ScreenCapturer, brain: Brain, executor: ActionExecutor,
                 gate: ConfirmationGate, log: EventLog, slow_notice_s: float = 1.5,
                 max_steps: int | None = None, settle_scale: float | None = None) -> None:
        self.listener, self.stt, self.speaker = listener, stt, speaker
        self.capturer, self.brain = capturer, brain
        self.executor, self.gate, self.log = executor, gate, log
        self.slow_notice_s = slow_notice_s
        self.max_steps = max_steps or int(os.getenv("ACCEX_MAX_STEPS", "10"))
        self.settle_scale = (settle_scale if settle_scale is not None
                             else float(os.getenv("ACCEX_SETTLE_SCALE", "1")))
        self.pending: tuple[Action, Screenshot | None, Task] | None = None
        self._pool = ThreadPoolExecutor(max_workers=2)
        self._shot: Future | None = None

    # ------------------------------------------------------------ loop
    def run(self) -> None:
        self._say(f"Accex is ready. Hold {hotkey_name()} and ask me anything.")
        while True:
            try:
                self.run_turn()
            except (KeyboardInterrupt, EOFError):
                break
        self._say("Goodbye.")
        self.speaker.wait(5)
        self._pool.shutdown(wait=False, cancel_futures=True)

    def run_turn(self) -> None:
        """One push-to-talk cycle, including any task it starts. Never raises except to
        stop the loop."""
        self._shot = None
        try:
            clip = self.listener.wait_for_utterance(self._on_start)
            t0 = time.perf_counter()
            self.speaker.cue("thinking")
            text = self.stt.transcribe(clip).strip()
            stt_ms = _ms(t0)
            self.log.log("transcript", text=text, ms=stt_ms)
            if not text:
                self._say("Sorry, I didn't catch that.")
            elif self.pending:
                self._handle_confirmation(text)
            else:
                self._handle_question(text, t0, stt_ms)
        except (KeyboardInterrupt, EOFError):
            raise
        except Interrupted:
            self.speaker.stop()
        except AccexError as e:
            self._fail("turn", str(e), e.spoken)
        except Exception as e:
            self._fail("turn", repr(e), GENERIC_ERROR)

    def _on_start(self) -> None:
        """Key went down: silence speech and grab the screen while the user talks."""
        self.speaker.stop()
        self.speaker.cue("listening")
        self._shot = self._pool.submit(self.capturer.capture)

    # ------------------------------------------------------------ turns
    def _handle_question(self, text: str, t0: float, stt_ms: int) -> None:
        t_cap = time.perf_counter()
        shot = self._screenshot()
        capture_ms = _ms(t_cap)

        t_llm = time.perf_counter()
        future = self._pool.submit(self.brain.ask, text, shot)
        try:
            resp = future.result(timeout=self.slow_notice_s)
        except FutureTimeout:
            self._say("One moment.")
            resp = future.result()
        llm_ms = _ms(t_llm)
        self._log_llm(resp, llm_ms, step=0)
        self.log.log("latency", stt_ms=stt_ms, capture_ms=capture_ms, llm_ms=llm_ms,
                     total_ms=_ms(t0))
        self._run_task(resp, shot, Task(), first=True)

    def _handle_confirmation(self, text: str) -> None:
        action, shot, task = self.pending  # type: ignore[misc]
        verdict = self.gate.classify(text)
        self.log.log("confirm", reply=text, verdict=verdict, action=action.type)
        if verdict == "yes":
            self.pending = None
            nxt = self._act_and_look(action, shot, task)
            if nxt:
                self._run_task(*nxt, task, first=False)
        elif verdict == "no":
            self.pending = None
            self.brain.record_action(action, ActionResult(False, "Cancelled by the user."))
            self._say("Okay, cancelled.")
            self._end(task, "cancelled")
        else:
            self._say("Please say yes or no.")

    # ------------------------------------------------------------ multi-step task
    def _run_task(self, resp: LLMResponse, shot: Screenshot | None, task: Task,
                  first: bool) -> None:
        """Speak the reply and keep acting until the task is done or must stop."""
        while True:
            say, action = resp.say.strip(), resp.action
            if not first:
                self._wait_speech()
            first = False

            if action is None:
                if say:
                    self._say(say)
                return self._end(task, "done")
            if self.gate.requires_confirmation(action, resp.needs_confirmation):
                if not say.endswith("?"):
                    say = f"{say} Should I go ahead?".strip()
                self.pending = (action, shot, task)
                self._say(say)
                return self._end(task, "confirm")
            if task.steps >= self.max_steps:
                self._say(f"I've done {task.steps} steps and stopped. "
                          "Say continue to keep going.")
                return self._end(task, "max_steps")
            sig = (action.type, json.dumps(action.params, sort_keys=True, default=str))
            task.repeats = task.repeats + 1 if sig == task.last else 1
            task.last = sig
            if task.repeats >= MAX_REPEATS:
                self._say("I seem to be stuck repeating the same step, so I stopped.")
                return self._end(task, "stuck")

            if say:
                self._say(say)
            nxt = self._act_and_look(action, shot, task)
            if nxt is None:
                return
            resp, shot = nxt

    def _act_and_look(self, action: Action, shot: Screenshot | None,
                      task: Task) -> tuple[LLMResponse, Screenshot | None] | None:
        """Run one action, let the screen settle, look again and ask for the next step.
        Returns None if the task ended here."""
        result = self._execute(action, shot)
        task.steps += 1
        task.failures = 0 if result.ok else task.failures + 1
        if task.failures >= MAX_FAILURES:
            self._wait_speech()
            self._say("I couldn't finish this task.")
            self._end(task, "failed")
            return None
        self._settle(action.type)

        self._shot = None
        shot = self._screenshot()
        self._check_interrupt()
        t = time.perf_counter()
        future = self._pool.submit(self.brain.ask, CONTINUE, shot)
        while True:
            try:
                resp = future.result(timeout=0.05)
                break
            except FutureTimeout:
                self._check_interrupt()
        self._log_llm(resp, _ms(t), step=task.steps)
        return resp, shot

    def _end(self, task: Task, reason: str) -> None:
        self.log.log("task_end", reason=reason, steps=task.steps, ms=_ms(task.t0))

    # ------------------------------------------------------------ interruption
    def _interrupted(self) -> bool:
        check = getattr(self.listener, "interrupted", None)   # optional listener method
        try:
            return bool(check and check())
        except Exception:
            return False

    def _check_interrupt(self) -> None:
        if self._interrupted():
            self.speaker.stop()
            self.log.log("task_end", reason="interrupted")
            raise Interrupted()

    def _settle(self, action_type: str) -> None:
        delay = SETTLE_S.get(action_type, DEFAULT_SETTLE_S) * self.settle_scale
        deadline = time.monotonic() + delay
        while True:
            self._check_interrupt()
            left = deadline - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(0.05, left))

    def _wait_speech(self) -> None:
        """Let the previous line finish (say() would cut it off), but stop at once if the
        user presses the key."""
        deadline = time.monotonic() + SPEECH_WAIT_S
        while time.monotonic() < deadline:
            self._check_interrupt()
            t = time.monotonic()
            self.speaker.wait(0.1)
            if time.monotonic() - t < 0.09:      # returned early: nothing is playing
                return

    # ------------------------------------------------------------ helpers
    def _screenshot(self) -> Screenshot | None:
        """Result of the capture started at key-down; None (and logged) if it failed."""
        try:
            future = self._shot or self._pool.submit(self.capturer.capture)
            return future.result(timeout=5)
        except Exception as e:
            self.log.log("error", where="capture", detail=repr(e))
            return None

    def _execute(self, action: Action, shot: Screenshot | None) -> ActionResult:
        self.log.log("action", type=action.type, params=action.params)
        t = time.perf_counter()
        result = self.executor.execute(action, shot)
        self.log.log("action_result", ok=result.ok, message=result.message, ms=_ms(t))
        self.brain.record_action(action, result)
        if result.ok:
            self.speaker.cue("done")
        else:
            self.speaker.cue("error")
            self._wait_speech()
            self._say(result.message)
        return result

    def _log_llm(self, resp: LLMResponse, ms: int, step: int) -> None:
        self.log.log("llm", raw=resp.raw, say=resp.say, ms=ms, step=step,
                     action=resp.action and {"type": resp.action.type,
                                             "params": resp.action.params},
                     needs_confirmation=resp.needs_confirmation)

    def _say(self, text: str) -> None:
        self.log.log("say", text=text)
        self.speaker.say(text)

    def _fail(self, where: str, detail: str, spoken: str) -> None:
        self.log.log("error", where=where, detail=detail)
        try:
            self.speaker.cue("error")
            self._say(spoken)
        except Exception as e:  # the speaker itself is broken: at least print
            print(f"[ERROR] {spoken} ({detail}; speaker failed: {e!r})", file=sys.stderr)


# ---------------------------------------------------------------- profiles
# Senior profile: brisk, clear voice settings, copied onto the existing knobs
# before the voice is built. The default profile changes nothing.
SENIOR_SETTINGS = {  # senior variable -> (existing variable it sets, default value)
    "ACCEX_SENIOR_ELEVEN_SPEED": ("ACCEX_ELEVEN_SPEED", "1.1"),
    "ACCEX_SENIOR_TTS_RATE": ("ACCEX_TTS_RATE", "1"),
    "ACCEX_SENIOR_STT_MIN_RMS": ("ACCEX_STT_MIN_RMS", "30"),
}


def apply_profile(env=os.environ) -> str:
    """Apply ACCEX_PROFILE to the environment; returns the active profile name."""
    if env.get("ACCEX_PROFILE", "default").strip().lower() != "senior":
        return "default"
    for senior_var, (target, default) in SENIOR_SETTINGS.items():
        env[target] = env.get(senior_var) or default
    return "senior"


def share_vocabulary(assistant: "Assistant") -> int:
    """Senior mode: pass family names to speech recognition if it supports
    set_vocabulary(words) (optional hook in voice/stt.py). Returns how many were sent."""
    senior = getattr(assistant.brain, "senior", None)
    hook = getattr(assistant.stt, "set_vocabulary", None)
    words = senior.vocabulary() if senior is not None else []
    if not (hook and words):
        return 0
    try:
        hook(words)
    except Exception as e:
        assistant.log.log("error", where="set_vocabulary", detail=repr(e))
        return 0
    return len(words)


# ---------------------------------------------------------------- wiring
def parse_mocks(value: str) -> set[str]:
    parts = {p.strip().lower() for p in value.split(",") if p.strip()}
    if "all" in parts:
        return set(PACKAGES)
    unknown = parts - set(PACKAGES)
    if unknown:
        raise SystemExit(f"Unknown --mock value(s): {', '.join(sorted(unknown))}. "
                         f"Use all or any of: {', '.join(PACKAGES)}")
    return parts


def build(mocked: set[str]) -> Assistant:
    mod = {p: importlib.import_module(f"mocks.{p}" if p in mocked else p) for p in PACKAGES}
    executor = mod["actions"].create_executor()
    return Assistant(
        listener=mod["voice"].create_listener(),
        stt=mod["voice"].create_stt(),
        speaker=mod["voice"].create_speaker(),
        capturer=mod["brain"].create_capturer(),
        brain=mod["brain"].create_brain(executor.specs()),
        executor=executor,
        gate=mod["actions"].create_gate(),
        log=mod["demo"].create_log(),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser(description="Accex - voice-first computer assistant")
    ap.add_argument("--mock", default=os.getenv("ACCEX_MOCK", ""),
                    help="comma list of packages to mock: all, voice, brain, actions, demo")
    ap.add_argument("--demo", action="store_true", help="verbose event log (ACCEX_DEMO=1)")
    ap.add_argument("--dry-run", action="store_true", help="log actions instead of running them")
    ap.add_argument("--ui", action="store_true", default=os.getenv("ACCEX_UI", "0") == "1",
                    help="show the floating glass pill (ACCEX_UI=1)")
    args = ap.parse_args(argv)
    if args.demo:
        os.environ["ACCEX_DEMO"] = "1"
    if args.dry_run:
        os.environ["ACCEX_DRY_RUN"] = "1"

    mocked = parse_mocks(args.mock)
    profile = apply_profile()

    def make() -> Assistant:
        assistant = build(mocked)
        if profile == "senior":
            senior = getattr(assistant.brain, "senior", None)
            people = len((senior.profile or {}).get("family", [])) if senior else 0
            hints = share_vocabulary(assistant)
            print(f"Senior mode on: {people} family members in the profile, "
                  f"{hints} names sent to speech recognition.")
        real = [p for p in PACKAGES if p not in mocked]
        print(f"Accex starting. Real: {', '.join(real) or 'none'}. "
              f"Mocked: {', '.join(p for p in PACKAGES if p in mocked) or 'none'}.")
        return assistant

    if args.ui:
        from ui.app import run_with_pill
        return run_with_pill(make, {"profile": profile, "hotkey": hotkey_name()})

    try:
        assistant = make()
    except NotImplementedError as e:
        print(f"Not implemented yet: {e}", file=sys.stderr)
        return 1
    except AccexError as e:
        print(f"Startup failed: {e.spoken} ({e})", file=sys.stderr)
        return 1
    assistant.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
