"""Voice confirmation gate (owner: P3). Implements interfaces.ConfirmationGate.

requires_confirmation = model flag OR the action's spec is dangerous. The second part
is the prompt-injection defense: a dangerous action is confirmed even if the model
(or text on the screen) says it doesn't need to be.

classify() is pure keyword logic. Negation always wins, so "no, don't send it",
"wait" or "yes... no, stop" are all "no". Anything without a clear yes is "unclear".
"""
from __future__ import annotations

import re

from interfaces import Action, ActionSpec, Confirmation

# Multi-word phrases are matched on word boundaries against the normalized reply.
NO_PHRASES = (
    "no", "nope", "nah", "not", "never", "don't", "do not", "dont", "cancel", "stop",
    "wait", "hold on", "hang on", "abort", "negative", "nevermind", "never mind",
    "forget it", "not yet", "no way",
)
YES_PHRASES = (
    "yes", "yeah", "yep", "yup", "yea", "ya", "sure", "ok", "okay", "alright", "all right",
    "confirm", "confirmed", "correct", "affirmative", "absolutely", "definitely",
    "of course", "please do", "do it", "go ahead", "go for it", "send it", "send",
    "proceed", "continue", "that's right", "right", "fine",
)


def _pattern(phrases: tuple[str, ...]) -> re.Pattern[str]:
    alts = sorted((re.escape(p).replace(r"\ ", r"\s+") for p in phrases), key=len, reverse=True)
    return re.compile(r"(?<![a-z'])(?:" + "|".join(alts) + r")(?![a-z'])")


_NO = _pattern(NO_PHRASES)
_YES = _pattern(YES_PHRASES)


def normalize(reply: str) -> str:
    text = reply.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z' ]+", " ", text)
    return " ".join(text.split())


class KeywordGate:
    def __init__(self, specs: list[ActionSpec] | None = None) -> None:
        if specs is None:
            from . import builtin  # noqa: F401  (registers the built-in actions)
            from .registry import REGISTRY
            specs = [entry.spec for entry in REGISTRY.values()]
        self._dangerous = {s.name for s in specs if s.dangerous}

    def requires_confirmation(self, action: Action, model_flag: bool) -> bool:
        return bool(model_flag) or action.type in self._dangerous

    def classify(self, reply: str) -> Confirmation:
        text = normalize(reply)
        if not text:
            return "unclear"
        if _NO.search(text):
            return "no"
        if _YES.search(text):
            return "yes"
        return "unclear"
