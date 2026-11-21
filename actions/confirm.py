"""Voice confirmation gate (owner: P3). Implements interfaces.ConfirmationGate.

TODO(P3): requires_confirmation = model_flag OR spec.dangerous (read from the registry).
classify(): keyword/phrase matching, negation wins ("no, don't send it" -> "no"),
"do it" / "go ahead" / "send it" -> "yes", anything else -> "unclear". Unit-test a table.
"""
from __future__ import annotations

from interfaces import Action, Confirmation


class KeywordGate:
    def __init__(self) -> None:
        raise NotImplementedError("actions.KeywordGate (P3) - run with --mock actions")

    def requires_confirmation(self, action: Action, model_flag: bool) -> bool:
        raise NotImplementedError

    def classify(self, reply: str) -> Confirmation:
        raise NotImplementedError
