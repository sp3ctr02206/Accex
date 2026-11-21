"""Confirmation gate: reply table + dangerous-action rule."""
from __future__ import annotations

import pytest

from actions.confirm import KeywordGate
from interfaces import Action, ActionSpec

GATE = KeywordGate()

TABLE = [
    # yes
    ("Yes.", "yes"), ("yes", "yes"), ("YES!", "yes"), ("Yeah", "yes"), ("yep", "yes"),
    ("Sure.", "yes"), ("okay", "yes"), ("OK", "yes"), ("Do it.", "yes"), ("Go ahead.", "yes"),
    ("Send it.", "yes"), ("Yes, send it.", "yes"), ("Please do", "yes"), ("go for it", "yes"),
    ("Confirm", "yes"), ("Absolutely", "yes"), ("of course", "yes"), ("alright", "yes"),
    ("All right then.", "yes"), ("That's right", "yes"), ("yes please", "yes"),
    # no (negation wins)
    ("No.", "no"), ("no", "no"), ("Nope", "no"), ("nah", "no"), ("Cancel", "no"),
    ("Stop!", "no"), ("Wait", "no"), ("Hold on", "no"), ("No, don't send it.", "no"),
    ("Don't send it", "no"), ("don’t do it", "no"), ("Do not send", "no"),
    ("Yes... no, stop.", "no"), ("Yeah, no.", "no"), ("not yet", "no"), ("never mind", "no"),
    ("Of course not", "no"), ("Forget it", "no"), ("I don't know", "no"),
    # unclear
    ("maybe", "unclear"), ("", "unclear"), ("   ", "unclear"), ("What did it say?", "unclear"),
    ("Read it again", "unclear"), ("hmm", "unclear"), ("tomorrow", "unclear"),
    # words that only contain yes/no letters must not match
    ("I know", "unclear"), ("notebook", "unclear"), ("noted", "unclear"), ("eyes", "unclear"),
    ("sender", "unclear"), ("stopwatch", "unclear"), ("gopher", "unclear"),
]


@pytest.mark.parametrize("reply,expected", TABLE)
def test_classify(reply, expected):
    assert GATE.classify(reply) == expected


def test_dangerous_always_confirmed():
    assert GATE.requires_confirmation(Action("email_reply", {"body": "x"}), model_flag=False)


def test_safe_action_follows_model_flag():
    a = Action("scroll", {"direction": "down"})
    assert not GATE.requires_confirmation(a, model_flag=False)
    assert GATE.requires_confirmation(a, model_flag=True)


def test_custom_specs():
    gate = KeywordGate([ActionSpec("delete_file", "", {}, dangerous=True)])
    assert gate.requires_confirmation(Action("delete_file"), False)
    assert not gate.requires_confirmation(Action("email_reply"), False)
