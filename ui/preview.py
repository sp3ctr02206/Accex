"""Design preview of the pill with scripted events (no assistant, no API).

    python -m ui.preview                      # plays every state in a loop
    python -m ui.preview --stop-at 9 --shot out.png   # stop at frame 9, save a screenshot

The preview window is capturable (ACCEX_UI_CAPTURABLE=1) so it can be screenshotted.
"""
from __future__ import annotations

import argparse
import os
import time

FRAMES: list[tuple[float, str, dict]] = [
    (0.6, "hello", {"profile": "senior", "hotkey": "Alt Gr"}),
    (1.6, "cue", {"name": "listening"}),
    (2.0, "cue", {"name": "thinking"}),
    (0.4, "transcript", {"text": "Play Bohemian Rhapsody by Queen on Spotify"}),
    (1.0, "say", {"text": "Opening Spotify."}),
    (1.4, "action", {"type": "open_app", "params": {"name": "Spotify"}}),
    (1.4, "action", {"type": "click", "params": {"target": "Spotify search box"}}),
    (1.4, "action", {"type": "type_text", "params": {"text": "Bohemian Rhapsody Queen"}}),
    (1.4, "action", {"type": "press_key", "params": {"keys": "enter"}}),
    (0.4, "say", {"text": "Bohemian Rhapsody by Queen is now playing on Spotify."}),
    (5.5, "task_end", {"reason": "done", "steps": 4}),
    (1.2, "cue", {"name": "listening"}),
    (1.2, "cue", {"name": "thinking"}),
    (0.4, "transcript", {"text": "Lucas needs help, what should I do?"}),
    (0.8, "say", {"text": "Stop. This looks like a scam: fake grandson email asking for "
                          "gift cards. Don't click, call or pay anything."}),
    (6.0, "task_end", {"reason": "done", "steps": 0}),
    (1.2, "cue", {"name": "listening"}),
    (1.2, "cue", {"name": "thinking"}),
    (0.4, "transcript", {"text": "Call the grandkids"}),
    (0.8, "say", {"text": "Which grandchild should I call, Lucas or Sofia?"}),
    (6.0, "task_end", {"reason": "done", "steps": 0}),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop-at", type=int, help="stop after this frame index")
    ap.add_argument("--shot", help="save a screenshot (png) after stopping, then exit")
    args = ap.parse_args()
    os.environ["ACCEX_UI_CAPTURABLE"] = "1"

    from ui.app import open_pill

    def play(bridge, window) -> None:
        loop = args.stop_at is None
        while True:
            for i, (delay, kind, data) in enumerate(FRAMES):
                time.sleep(delay)
                bridge.emit(kind, **data)
                if args.stop_at is not None and i >= args.stop_at:
                    if args.shot:
                        time.sleep(1.4)               # let the animations settle
                        _screenshot(args.shot)
                        window.destroy()
                    return
            if not loop:
                return

    open_pill(play, title="Accex preview")
    return 0


def _screenshot(path: str) -> None:
    import ctypes
    from ctypes import wintypes

    import mss
    import mss.tools
    hwnd = ctypes.windll.user32.FindWindowW(None, "Accex preview")
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print(f"window rect (physical px): {rect.left},{rect.top} -> {rect.right},{rect.bottom}")
    factory = getattr(mss, "MSS", None) or mss.mss
    with factory() as sct:
        mon = sct.monitors[1]
        w, h = 900, 420
        region = {"left": mon["left"] + (mon["width"] - w) // 2,
                  "top": mon["top"] + mon["height"] - h, "width": w, "height": h}
        mss.tools.to_png(sct.grab(region).rgb, (w, h), output=path)


if __name__ == "__main__":
    raise SystemExit(main())
