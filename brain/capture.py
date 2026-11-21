"""Screen capture (owner: P2). Implements interfaces.ScreenCapturer.

Grabs the primary monitor with mss, downsizes it with Pillow so the longest side is
<= ACCEX_SCREEN_MAX_SIDE (default 1280) and encodes it as JPEG in memory. Nothing is
written to disk. main.py sets DPI awareness first, so these are physical pixels.
"""
from __future__ import annotations

import io
import os

from interfaces import AccexError, Screenshot


def _open_mss():
    import mss
    factory = getattr(mss, "MSS", None) or mss.mss  # mss >= 10 renamed mss.mss -> mss.MSS
    return factory()


def _primary(monitors: list[dict]) -> dict:
    for mon in monitors[1:]:
        if mon.get("is_primary"):
            return mon
    return monitors[1] if len(monitors) > 1 else monitors[0]


def encode(img, left: int, top: int, max_side: int, quality: int) -> Screenshot:
    """Downscale a PIL image and wrap it as a Screenshot (separate for testing)."""
    from PIL import Image

    screen_w, screen_h = img.size
    scale = min(1.0, max_side / max(screen_w, screen_h))
    if scale < 1.0:
        img = img.resize((round(screen_w * scale), round(screen_h * scale)),
                         Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return Screenshot(jpeg_bytes=buf.getvalue(), width=img.width, height=img.height,
                      screen_left=left, screen_top=top,
                      screen_width=screen_w, screen_height=screen_h)


class MssCapturer:
    def __init__(self) -> None:
        self.max_side = int(os.getenv("ACCEX_SCREEN_MAX_SIDE", "1280"))
        self.quality = int(os.getenv("ACCEX_SCREEN_QUALITY", "80"))
        import mss  # noqa: F401  fail at startup, not mid-demo, if missing
        from PIL import Image  # noqa: F401

    def capture(self) -> Screenshot:
        from PIL import Image
        try:
            # A new mss instance per call: its handles are bound to the calling thread.
            with _open_mss() as sct:
                mon = _primary(sct.monitors)
                raw = sct.grab(mon)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return encode(img, mon["left"], mon["top"], self.max_side, self.quality)
        except Exception as e:
            raise AccexError("I couldn't see the screen.", f"capture failed: {e!r}") from e
