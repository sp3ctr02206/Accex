import sys

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from brain.capture import encode  # noqa: E402


def test_encode_downscales_and_keeps_geometry():
    shot = encode(Image.new("RGB", (2560, 1600), "white"), 0, 0, 1280, 80)
    assert (shot.width, shot.height) == (1280, 800)
    assert (shot.screen_width, shot.screen_height) == (2560, 1600)
    assert shot.jpeg_bytes[:2] == b"\xff\xd8"
    assert shot.to_screen(640, 400) == (1280, 800)


def test_encode_never_upscales():
    shot = encode(Image.new("RGB", (800, 600)), 10, 20, 1280, 80)
    assert (shot.width, shot.height) == (800, 600)
    assert shot.to_screen(0, 0) == (10, 20)


@pytest.mark.skipif(sys.platform != "win32", reason="real capture is checked on the demo OS")
def test_real_capture():
    pytest.importorskip("mss")
    from brain.capture import MssCapturer
    shot = MssCapturer().capture()
    assert max(shot.width, shot.height) <= 1280 and len(shot.jpeg_bytes) > 1000
