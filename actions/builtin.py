"""Built-in actions (owner: P3). Each one is a single @action-decorated function.

GUI libraries (pyautogui, pyperclip) are imported lazily through _gui() / _clip()
so the unit tests run without them, and so tests can swap in fakes.
"""
from __future__ import annotations

import os
import shutil
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from interfaces import AccexError

from .registry import action

# ------------------------------------------------------------ helpers
_gui_mod = None


def _gui():
    """pyautogui, configured once. FAILSAFE stays on: mouse to a corner aborts."""
    global _gui_mod
    if _gui_mod is None:
        try:
            import pyautogui
        except ImportError as e:
            raise AccexError("Keyboard and mouse control isn't available.", repr(e))
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        _gui_mod = pyautogui
    return _gui_mod


def _clip():
    try:
        import pyperclip
    except ImportError as e:
        raise AccexError("The clipboard isn't available.", repr(e))
    return pyperclip


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _demo() -> bool:
    return os.getenv("ACCEX_DEMO", "0") == "1"


def paste_text(text: str) -> None:
    """Type any Unicode text by pasting it, then restore the user's clipboard.
    (pyautogui.write is ASCII-only.)"""
    clip = _clip()
    try:
        previous = clip.paste()
    except Exception:
        previous = None
    try:
        clip.copy(text)
    except Exception as e:
        raise AccexError("I couldn't use the clipboard to type.", repr(e))
    _gui().hotkey("ctrl", "v")
    _sleep(0.3)  # let the target app read the clipboard before we restore it
    if previous is not None:
        try:
            clip.copy(previous)
        except Exception:
            pass


# ------------------------------------------------------------ open_url
@action("open_url", "Open a web page in the default browser.",
        {"url": "full https URL, e.g. https://www.youtube.com"})
def open_url(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or "." not in parsed.netloc:
        raise AccexError("That doesn't look like a web address I can open.", f"url={url!r}")
    if not webbrowser.open(url):
        raise AccexError("I couldn't open the browser.", f"webbrowser.open({url!r}) returned False")
    host = parsed.netloc.removeprefix("www.")
    return f"Opening {host}."


# ------------------------------------------------------------ open_app
# Spoken name -> what os.startfile understands (exe on PATH, URI, or URL).
KNOWN_APPS: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "settings": "ms-settings:",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "browser": "https://www.google.com",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "spotify": "spotify:",
    "gmail": "https://mail.google.com",
    "youtube": "https://www.youtube.com",
}

# Demo mode: absolute paths that are known to work on the demo laptop.
_PF = os.environ.get("ProgramFiles", r"C:\Program Files")
_PF86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
_LOCAL = os.environ.get("LOCALAPPDATA", "")
DEMO_PATHS: dict[str, list[str]] = {
    "chrome.exe": [rf"{_PF}\Google\Chrome\Application\chrome.exe",
                   rf"{_PF86}\Google\Chrome\Application\chrome.exe",
                   rf"{_LOCAL}\Google\Chrome\Application\chrome.exe"],
    "msedge.exe": [rf"{_PF86}\Microsoft\Edge\Application\msedge.exe",
                   rf"{_PF}\Microsoft\Edge\Application\msedge.exe"],
}

_FILLER = ("open ", "launch ", "start ", "the ", "app ", "application ", "program ")


def _normalize_app(name: str) -> str:
    name = " ".join(name.lower().strip(" .!?").split())
    changed = True
    while changed:
        changed = False
        for word in _FILLER:
            if name.startswith(word):
                name, changed = name[len(word):], True
    for suffix in (" app", " application", " program"):
        name = name.removesuffix(suffix)
    return name.strip()


def _resolve(target: str) -> str:
    """Best launchable form of target. In demo mode known absolute paths win.
    A bare exe name still works through Windows 'App Paths' (e.g. winword.exe)."""
    if ":" in target and not target.lower().endswith(".exe"):
        return target                       # URL or URI scheme (ms-settings:, spotify:)
    known = [p for p in DEMO_PATHS.get(target, []) if Path(p).is_file()]
    if _demo() and known:
        return known[0]
    return shutil.which(target) or (known[0] if known else target)


def _start(target: str) -> None:
    if target.startswith(("http://", "https://")):
        if not webbrowser.open(target):
            raise OSError(f"webbrowser.open({target!r}) failed")
        return
    os.startfile(target)  # type: ignore[attr-defined]  (Windows only)


def _start_menu(name: str) -> None:
    """Fallback: Win key -> type the name -> Enter."""
    gui = _gui()
    gui.press("win")
    _sleep(0.8)
    if name.isascii():
        gui.write(name, interval=0.02)
    else:
        paste_text(name)
    _sleep(1.0)
    gui.press("enter")


@action("open_app", "Open an application by name.",
        {"name": "app name, e.g. 'notepad', 'chrome', 'calculator', 'file explorer'"})
def open_app(name: str) -> str:
    app = _normalize_app(name)
    if not app:
        raise AccexError("Which app should I open?", f"name={name!r}")
    target = KNOWN_APPS.get(app)
    if target:
        try:
            _start(_resolve(target))
            return f"Opening {app}."
        except OSError:
            pass  # not installed under that name: fall through to the Start menu
    _start_menu(app)
    return f"Opening {app}."


# ------------------------------------------------------------ scroll
WHEEL_DELTA = 120  # pyautogui on Windows scrolls in raw wheel units


@action("scroll", "Scroll the active window up or down.",
        {"direction": "'up' or 'down'", "amount": "int, wheel clicks (default 5)"})
def scroll(direction: str, amount: int = 5) -> str:
    direction = direction.strip().lower()
    if direction not in ("up", "down"):
        raise AccexError("I can only scroll up or down.", f"direction={direction!r}")
    amount = max(1, min(abs(amount), 50))
    clicks = amount if direction == "up" else -amount
    _gui().scroll(clicks * WHEEL_DELTA)
    return f"Scrolled {direction}."


# ------------------------------------------------------------ press_key
KEY_ALIASES = {
    "control": "ctrl", "ctl": "ctrl", "return": "enter", "escape": "esc",
    "windows": "win", "window": "win", "super": "win", "cmd": "win",
    "del": "delete", "page down": "pagedown", "page up": "pageup",
    "pgdn": "pagedown", "pgup": "pageup", "spacebar": "space", "arrow up": "up",
    "arrow down": "down", "arrow left": "left", "arrow right": "right",
    "up arrow": "up", "down arrow": "down", "left arrow": "left", "right arrow": "right",
    "option": "alt", "caps lock": "capslock", "print screen": "printscreen",
}


def parse_keys(keys: str) -> list[str]:
    """'Ctrl + Enter' -> ['ctrl', 'enter']; aliases are normalized."""
    parts = [" ".join(p.lower().split()) for p in keys.replace("-", "+").split("+")]
    parts = [KEY_ALIASES.get(p, p) for p in parts if p]
    if not parts:
        raise AccexError("Which key should I press?", f"keys={keys!r}")
    return parts


@action("press_key", "Press a key or a keyboard shortcut.",
        {"keys": "key or shortcut joined with '+', e.g. 'enter', 'tab', 'ctrl+enter', 'alt+left'"})
def press_key(keys: str) -> str:
    parts = parse_keys(keys)
    gui = _gui()
    valid = set(getattr(gui, "KEYBOARD_KEYS", []))
    bad = [p for p in parts if valid and p not in valid]
    if bad:
        raise AccexError(f"I don't know the key {bad[0]}.", f"keys={keys!r}")
    if len(parts) == 1:
        gui.press(parts[0])
    else:
        gui.hotkey(*parts)
    return f"Pressed {' plus '.join(parts)}."


# ------------------------------------------------------------ type_text
@action("type_text", "Type text into the focused field.", {"text": "the text to type"})
def type_text(text: str) -> str:
    if not text:
        raise AccexError("What should I type?", "empty text")
    paste_text(text)
    return "Typed it."


# ------------------------------------------------------------ click
@action("click", "Click a point on the screen.",
        {"x": "int, image pixels from the left", "y": "int, image pixels from the top",
         "target": "short name of what is clicked, e.g. 'Compose button'"},
        coords=True)
def click(x: int, y: int, target: str = "") -> str:
    _gui().click(x, y)
    target = target.strip()
    return f"Clicked {target}." if target else "Clicked."


# ------------------------------------------------------------ email_reply
GMAIL_REPLY_WAIT_S = 1.5
GMAIL_SEND_WAIT_S = 1.0


@action("email_reply",
        "Reply to the email that is open in Gmail and send it. Use only when an email is open.",
        {"body": "the reply text"}, dangerous=True)
def email_reply(body: str) -> str:
    body = body.strip()
    if not body:
        raise AccexError("What should the reply say?", "empty body")
    gui = _gui()
    gui.press("r")                    # Gmail shortcut: reply (needs keyboard shortcuts on)
    _sleep(GMAIL_REPLY_WAIT_S)
    paste_text(body)
    _sleep(0.3)
    gui.hotkey("ctrl", "enter")       # Gmail: send
    _sleep(GMAIL_SEND_WAIT_S)
    return "Email sent."


# ------------------------------------------------------------ wait
@action("wait", "Wait for a page or app that is still loading, then look again.",
        {"seconds": "float, how long to wait, 0.5 to 5 (default 2)"})
def wait(seconds: float = 2.0) -> str:
    _sleep(max(0.5, min(seconds, 5.0)))
    return "Waited."
