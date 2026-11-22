"""The floating glass pill window (pywebview + Edge WebView2).

The window:
- is frameless, always on top and never activated (Accex types into the user's app);
- is cut to the pill's exact size and rounded shape (SetWindowRgn) every time the pill
  changes, so there is no box around it;
- is click-through (WS_EX_LAYERED | WS_EX_TRANSPARENT): clicks, including Accex's own,
  always reach the app underneath;
- is excluded from screen capture, so Accex's own screenshots never contain it.
  Set ACCEX_UI_CAPTURABLE=1 to allow capture, e.g. to record a demo video (the model
  will then see the pill as well).

Windows only blurs the desktop behind *active* windows, and this one never activates,
so the glass is drawn by CSS (Apple-style dark material) rather than a live blur.

The assistant runs in a worker thread; the GUI loop owns the main thread.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

from interfaces import AccexError

from .bridge import TapLog, TapSpeaker, UiBridge

WEB = Path(__file__).resolve().parent / "web" / "index.html"
GLASS_HEX = "#1E1F26"                # window colour = pill base colour (style.css --glass)
START_W, START_H = 320, 60           # logical pixels; the page refits it to the pill
BOTTOM_GAP = 16                      # logical pixels above the taskbar
WDA_EXCLUDEFROMCAPTURE = 0x11


def _scale() -> float:
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96
    except Exception:
        return 1.0


def _work_area() -> tuple[int, int, int, int]:
    """Desktop area without the taskbar, in physical pixels (left, top, right, bottom)."""
    rect = wintypes.RECT()
    try:
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return 0, 0, 1920, 1040


def bottom_center(width: int, height: int) -> tuple[int, int]:
    """Logical x, y that put a width x height window centred above the taskbar."""
    s = _scale()
    left, _, right, bottom = _work_area()
    x = (left + right) / s / 2 - width / 2
    y = bottom / s - height - BOTTOM_GAP
    return int(x), int(y)


def exclude_from_capture(hwnd: int) -> bool:
    """Hide the window from screenshots and screen recordings (Windows 10 2004+)."""
    if os.getenv("ACCEX_UI_CAPTURABLE") == "1" or sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


def make_click_through(hwnd: int) -> bool:
    """Let every click pass through to the window underneath. The model cannot see the
    pill (it is excluded from capture), so it must not be able to block Accex's clicks."""
    if sys.platform != "win32":
        return False
    u = ctypes.windll.user32
    gwl_exstyle, ws_ex_layered, ws_ex_transparent, lwa_alpha = -20, 0x80000, 0x20, 0x2
    try:
        style = u.GetWindowLongW(hwnd, gwl_exstyle)
        u.SetWindowLongW(hwnd, gwl_exstyle, style | ws_ex_layered | ws_ex_transparent)
        return bool(u.SetLayeredWindowAttributes(hwnd, 0, 255, lwa_alpha))
    except Exception:
        return False


def on_shown(window) -> None:
    hwnd = window.native.Handle.ToInt32()
    make_click_through(hwnd)
    exclude_from_capture(hwnd)
    shape_window(hwnd, START_W, START_H, 30)


class PillApi:
    """Called from the page (window.pywebview.api). Attributes are private so pywebview
    does not try to expose the native window object to JavaScript."""

    def __init__(self) -> None:
        self._window = None
        self._size = (START_W, START_H)

    def fit(self, width: float, height: float, radius: float = 30) -> None:
        """Size the window to the pill and cut it to the pill's rounded shape."""
        w, h = int(width), int(height)
        if self._window is None:
            return
        try:
            # Always apply: the window Windows creates is not exactly START_W x START_H.
            self._size = (w, h)
            x, y = bottom_center(w, h)
            self._window.resize(w, h)
            self._window.move(x, y)
            shape_window(self._window.native.Handle.ToInt32(), w, h, radius)
        except Exception:
            pass


def shape_window(hwnd: int, width: int, height: int, radius: float) -> bool:
    """Clip the window to a rounded rectangle (logical sizes); outside it the window
    does not exist, so it is invisible and clicks go to whatever is underneath."""
    if sys.platform != "win32":
        return False
    s = _scale()
    w, h, d = round(width * s), round(height * s), round(2 * radius * s)
    rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, d, d)
    return bool(ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True))


def open_pill(on_ready: Callable[[UiBridge, Any], None], title: str = "Accex") -> None:
    """Create the pill window and run the GUI loop (blocks). on_ready(bridge, window) runs
    in a worker thread once the page has loaded."""
    import webview

    bridge = UiBridge()
    api = PillApi()
    x, y = bottom_center(START_W, START_H)
    window = webview.create_window(
        title, url=WEB.as_uri(), js_api=api, width=START_W, height=START_H, x=x, y=y,
        min_size=(120, 40),               # pywebview's default minimum is 200 x 100
        frameless=True, easy_drag=False, on_top=True, focus=False, resizable=False,
        shadow=False, text_select=False, zoomable=False, background_color=GLASS_HEX)
    api._window = window

    def loaded() -> None:
        bridge.attach(lambda js: window.evaluate_js(js))
        threading.Thread(target=on_ready, args=(bridge, window), name="accex-assistant",
                         daemon=True).start()

    window.events.shown += lambda: on_shown(window)
    window.events.loaded += loaded
    webview.start()
    bridge.close()


def run_with_pill(make_assistant: Callable[[], Any], hello: dict) -> int:
    """Build and run the assistant in a worker thread while the pill shows its state."""

    def worker(bridge: UiBridge, window) -> None:
        try:
            assistant = make_assistant()
        except (NotImplementedError, AccexError) as e:
            detail = getattr(e, "spoken", None) or str(e)
            print(f"Startup failed: {detail}", file=sys.stderr)
            bridge.emit("error", where="startup", detail=detail)
            return
        assistant.log = TapLog(assistant.log, bridge)
        assistant.speaker = TapSpeaker(assistant.speaker, bridge)
        bridge.emit("hello", **hello)
        try:
            assistant.run()
        finally:
            bridge.close()
            window.destroy()

    open_pill(worker)
    return 0
