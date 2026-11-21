"""Manual test of the real brain against the real screen (owner: P2).

    python -m brain.try_brain "What's on my screen?" "Which month had the highest sales?"
    python -m brain.try_brain --delay 3          # interactive; 3 s to switch windows first
    python -m brain.try_brain --image shot.png "What does this chart show?"

Prints the model's JSON and the latency of each stage. Needs ANTHROPIC_API_KEY (or the
provider configured in .env). Actions are only printed, never executed.
"""
from __future__ import annotations

import ctypes
import sys

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

import argparse
import time

from interfaces import AccexError


def _specs():
    try:
        import actions
        return actions.create_executor().specs()
    except Exception:  # real actions not built yet: use the planned catalog
        from mocks.actions import DEMO_SPECS
        return DEMO_SPECS


def _questions(args):
    yield from args.questions
    if not args.questions:
        while True:
            try:
                q = input("\nQuestion (empty to quit) > ").strip()
            except EOFError:
                return
            if not q:
                return
            yield q


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("questions", nargs="*")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to wait before each capture")
    ap.add_argument("--image", help="use this image file instead of the screen")
    args = ap.parse_args()

    from brain.brain import VisionBrain
    from brain.capture import MssCapturer, encode

    try:
        brain = VisionBrain(_specs())
    except AccexError as e:
        print(f"Setup failed: {e.spoken} ({e})")
        return 1
    print(f"Provider: {type(brain.provider).__name__}, model: {brain.provider.model}")
    capturer = MssCapturer()

    for q in _questions(args):
        if args.delay:
            print(f"Capturing in {args.delay:g} s...")
            time.sleep(args.delay)
        t0 = time.perf_counter()
        if args.image:
            from PIL import Image
            shot = encode(Image.open(args.image), 0, 0, capturer.max_side, capturer.quality)
        else:
            shot = capturer.capture()
        t1 = time.perf_counter()
        try:
            resp = brain.ask(q, shot)
        except AccexError as e:
            print(f"ERROR (spoken): {e.spoken}\n  detail: {e}")
            continue
        t2 = time.perf_counter()
        print(f"\nQ: {q}")
        print(f"say: {resp.say}")
        if resp.action:
            print(f"action: {resp.action.type} {resp.action.params}  "
                  f"needs_confirmation={resp.needs_confirmation}")
        print(f"image {shot.width}x{shot.height} {len(shot.jpeg_bytes) // 1024} KB | "
              f"capture {round((t1 - t0) * 1000)} ms | llm {round((t2 - t1) * 1000)} ms")
        if resp.raw.strip() and not resp.raw.lstrip().startswith("{"):
            print(f"(raw reply was not pure JSON: {resp.raw[:200]!r})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
