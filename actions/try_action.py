"""Run one action by hand (owner: P3).

    python -m actions.try_action --list
    python -m actions.try_action open_url url=https://example.com
    python -m actions.try_action scroll direction=down amount=3
    python -m actions.try_action click x=640 y=360 target="middle of the screen"
    python -m actions.try_action --dry-run email_reply body="Thanks, I'll review it tomorrow."
    python -m actions.try_action --delay 3 press_key keys=ctrl+l   # 3 s to focus a window

Coordinates for `click` are screen pixels here (the fake screenshot is the full screen).
"""
from __future__ import annotations

import ctypes
import sys

if sys.platform == "win32":  # same DPI setup as main.py, before pyautogui is imported
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

import argparse
import os
import time

from interfaces import Action, Screenshot


def _screen_shot() -> Screenshot:
    """A fake screenshot whose image space equals the physical screen."""
    try:
        import pyautogui
        w, h = pyautogui.size()
    except Exception:
        w, h = 1920, 1080
    return Screenshot(b"", w, h, 0, 0, w, h)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one Accex action")
    ap.add_argument("type", nargs="?", help="action name, e.g. open_url")
    ap.add_argument("params", nargs="*", help="key=value pairs")
    ap.add_argument("--list", action="store_true", help="list registered actions")
    ap.add_argument("--dry-run", action="store_true", help="log instead of acting")
    ap.add_argument("--delay", type=float, default=0, help="seconds to wait before acting")
    args = ap.parse_args(argv)

    os.environ.setdefault("ACCEX_DEMO", "1")
    if args.dry_run:
        os.environ["ACCEX_DRY_RUN"] = "1"

    from actions import create_executor, create_gate
    executor = create_executor()
    if args.list or not args.type:
        for s in executor.specs():
            flag = "  [dangerous]" if s.dangerous else ""
            print(f"{s.name}{flag}: {s.description}")
            for k, v in s.params.items():
                print(f"    {k}: {v}")
        return 0

    params = {}
    for pair in args.params:
        key, sep, value = pair.partition("=")
        if not sep:
            ap.error(f"expected key=value, got {pair!r}")
        params[key] = value
    act = Action(args.type, params)

    gate = create_gate()
    if gate.requires_confirmation(act, False):
        reply = input(f"{act.type} is dangerous. Type yes to run it: ")
        verdict = gate.classify(reply)
        print(f"gate: {verdict}")
        if verdict != "yes":
            print("cancelled")
            return 1

    if args.delay:
        print(f"acting in {args.delay:g} s...")
        time.sleep(args.delay)
    t0 = time.perf_counter()
    result = executor.execute(act, _screen_shot())
    print(f"ok={result.ok} message={result.message!r} ({(time.perf_counter() - t0) * 1000:.0f} ms)")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
