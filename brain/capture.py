"""Screen capture (owner: P2). Implements interfaces.ScreenCapturer.

TODO(P2): mss primary monitor (sct.monitors[1]) -> Pillow -> resize so the longest side
is <= ACCEX_SCREEN_MAX_SIDE (1280) -> JPEG quality ~80 in a BytesIO. Fill the Screenshot
geometry from the monitor dict. Never write to disk. Relies on main.py having set
DPI awareness first.
"""
from __future__ import annotations

from interfaces import Screenshot


class MssCapturer:
    def __init__(self) -> None:
        raise NotImplementedError("brain.MssCapturer (P2) - run with --mock brain")

    def capture(self) -> Screenshot:
        raise NotImplementedError
