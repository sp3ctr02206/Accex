"""Mock actions (owner: P3). Logs actions instead of running them."""
from __future__ import annotations

import re

from interfaces import Action, ActionResult, ActionSpec, Confirmation, Screenshot

# Mirrors actions/builtin.py exactly (actions/tests/test_mock_parity.py checks it),
# so the brain sees the same catalog with mocked and real actions.
DEMO_SPECS = [
    ActionSpec("open_url", "Open a web page in the default browser.",
               {"url": "full https URL, e.g. https://www.youtube.com"}),
    ActionSpec("open_app", "Open an application by name.",
               {"name": "app name, e.g. 'notepad', 'chrome', 'calculator', 'file explorer'"}),
    ActionSpec("scroll", "Scroll the active window up or down.",
               {"direction": "'up' or 'down'", "amount": "int, wheel clicks (default 5)"}),
    ActionSpec("press_key", "Press a key or a keyboard shortcut.",
               {"keys": "key or shortcut joined with '+', e.g. 'enter', 'tab', 'ctrl+enter', "
                        "'alt+left'"}),
    ActionSpec("type_text", "Type text into the focused field.", {"text": "the text to type"}),
    ActionSpec("click", "Click a point on the screen.",
               {"x": "int, image pixels from the left", "y": "int, image pixels from the top",
                "target": "short name of what is clicked, e.g. 'Compose button'"}),
    ActionSpec("email_reply",
               "Reply to the email that is open in Gmail and send it. "
               "Use only when an email is open.",
               {"body": "the reply text"}, dangerous=True),
]


class LoggingExecutor:
    def __init__(self, specs: list[ActionSpec] | None = None, quiet: bool = False) -> None:
        self._specs = list(specs if specs is not None else DEMO_SPECS)
        self.quiet = quiet
        self.executed: list[Action] = []

    def specs(self) -> list[ActionSpec]:
        return list(self._specs)

    def execute(self, action: Action, screenshot: Screenshot | None) -> ActionResult:
        if action.type not in {s.name for s in self._specs}:
            return ActionResult(False, f"I don't know how to {action.type.replace('_', ' ')}.")
        self.executed.append(action)
        if not self.quiet:
            print(f"[ACTION] {action.type} {action.params}")
        return ActionResult(True, "Done." if action.type != "email_reply" else "Email sent.")


_NO = {"no", "nope", "cancel", "stop", "don't", "dont", "not", "never", "wait"}
_YES = {"yes", "yeah", "yep", "sure", "ok", "okay", "send", "go", "confirm"}


class KeywordGate:
    def __init__(self, specs: list[ActionSpec] | None = None) -> None:
        self._dangerous = {s.name for s in (specs if specs is not None else DEMO_SPECS) if s.dangerous}

    def requires_confirmation(self, action: Action, model_flag: bool) -> bool:
        return model_flag or action.type in self._dangerous

    def classify(self, reply: str) -> Confirmation:
        words = set(re.findall(r"[a-z']+", reply.lower()))
        if words & _NO:          # negation wins: "no, don't send it" -> no
            return "no"
        if words & _YES:
            return "yes"
        return "unclear"


def create_executor() -> LoggingExecutor:
    return LoggingExecutor()


def create_gate() -> KeywordGate:
    return KeywordGate()
