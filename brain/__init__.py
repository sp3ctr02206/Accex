"""Brain package (owner: Person 2): screen capture, vision LLM, prompt, memory, parsing.

Factories are the only public API (see interfaces.py). Imports are lazy.
"""
from __future__ import annotations


def create_capturer():
    from .capture import MssCapturer
    return MssCapturer()


def create_brain(specs):
    from .brain import VisionBrain
    return VisionBrain(specs)
