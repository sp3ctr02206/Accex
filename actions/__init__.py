"""Actions package (owner: Person 3): action registry, executor, confirmation gate.

Factories are the only public API (see interfaces.py). Imports are lazy.
"""
from __future__ import annotations


def create_executor():
    from .executor import RegistryExecutor
    return RegistryExecutor()


def create_gate():
    from .confirm import KeywordGate
    return KeywordGate()
