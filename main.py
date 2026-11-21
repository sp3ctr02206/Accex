"""Accex entry point and orchestration loop (owner: Person 2).

    python main.py                         # everything real
    python main.py --mock all              # everything mocked: type questions in the terminal
    python main.py --mock brain,actions    # real voice, scripted brain, logged actions
    python main.py --demo --dry-run        # verbose event log; actions only logged

Loop: push-to-talk -> STT -> (screenshot taken in parallel) -> brain -> speak -> act,
with a spoken yes/no confirmation before any dangerous action.
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
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from interfaces import (AccexError, Action, ActionExecutor, ActionResult, Brain,
                        ConfirmationGate, EventLog, Listener, ScreenCapturer, Screenshot,
                        Speaker, SpeechToText)

PACKAGES = ("voice", "brain", "actions", "demo")
GENERIC_ERROR = "Something went wrong. Please try again."


def _ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


class Assistant:
    def __init__(self, listener: Listener, stt: SpeechToText, speaker: Speaker,
                 capturer: ScreenCapturer, brain: Brain, executor: ActionExecutor,
                 gate: ConfirmationGate, log: EventLog, slow_notice_s: float = 1.5) -> None:
        self.listener, self.stt, self.speaker = listener, stt, speaker
        self.capturer, self.brain = capturer, brain
        self.executor, self.gate, self.log = executor, gate, log
        self.slow_notice_s = slow_notice_s
        self.pending: tuple[Action, Screenshot | None] | None = None
        self._pool = ThreadPoolExecutor(max_workers=1)
        self._shot: Future | None = None

    # ------------------------------------------------------------ loop
    def run(self) -> None:
        self._say("Accex is ready. Hold right control and ask me anything.")
        while True:
            try:
                self.run_turn()
            except (KeyboardInterrupt, EOFError):
                break
        self._say("Goodbye.")
        self.speaker.wait(5)
        self._pool.shutdown(wait=False, cancel_futures=True)

    def run_turn(self) -> None:
        """One push-to-talk cycle. Never raises except to stop the loop."""
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
        self.log.log("llm", raw=resp.raw, say=resp.say, ms=llm_ms,
                     action=resp.action and {"type": resp.action.type, "params": resp.action.params},
                     needs_confirmation=resp.needs_confirmation)

        action = resp.action
        if action and self.gate.requires_confirmation(action, resp.needs_confirmation):
            say = resp.say.strip()
            if not say.endswith("?"):
                say = f"{say} Should I go ahead?".strip()
            self.pending = (action, shot)
            self._say(say)
        else:
            if resp.say.strip():
                self._say(resp.say)
            if action:
                self._execute(action, shot, speak_success=False)
        self.log.log("latency", stt_ms=stt_ms, capture_ms=capture_ms, llm_ms=llm_ms,
                     total_ms=_ms(t0))

    def _handle_confirmation(self, text: str) -> None:
        action, shot = self.pending  # type: ignore[misc]
        verdict = self.gate.classify(text)
        self.log.log("confirm", reply=text, verdict=verdict, action=action.type)
        if verdict == "yes":
            self.pending = None
            self._execute(action, shot, speak_success=True)
        elif verdict == "no":
            self.pending = None
            self.brain.record_action(action, ActionResult(False, "Cancelled by the user."))
            self._say("Okay, cancelled.")
        else:
            self._say("Please say yes or no.")

    # ------------------------------------------------------------ helpers
    def _screenshot(self) -> Screenshot | None:
        """Result of the capture started at key-down; None (and logged) if it failed."""
        try:
            future = self._shot or self._pool.submit(self.capturer.capture)
            return future.result(timeout=5)
        except Exception as e:
            self.log.log("error", where="capture", detail=repr(e))
            return None

    def _execute(self, action: Action, shot: Screenshot | None, speak_success: bool) -> None:
        self.log.log("action", type=action.type, params=action.params)
        t = time.perf_counter()
        result = self.executor.execute(action, shot)
        self.log.log("action_result", ok=result.ok, message=result.message, ms=_ms(t))
        self.brain.record_action(action, result)
        if result.ok:
            self.speaker.cue("done")
            if speak_success:
                self._say(result.message)
        else:
            self.speaker.cue("error")
            self._say(result.message)

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
    args = ap.parse_args(argv)
    if args.demo:
        os.environ["ACCEX_DEMO"] = "1"
    if args.dry_run:
        os.environ["ACCEX_DRY_RUN"] = "1"

    mocked = parse_mocks(args.mock)
    try:
        assistant = build(mocked)
    except NotImplementedError as e:
        print(f"Not implemented yet: {e}", file=sys.stderr)
        return 1
    except AccexError as e:
        print(f"Startup failed: {e.spoken} ({e})", file=sys.stderr)
        return 1

    real = [p for p in PACKAGES if p not in mocked]
    print(f"Accex starting. Real: {', '.join(real) or 'none'}. "
          f"Mocked: {', '.join(p for p in PACKAGES if p in mocked) or 'none'}.")
    assistant.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
