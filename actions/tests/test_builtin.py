"""Built-in actions against fake pyautogui / pyperclip / webbrowser (nothing real moves)."""
from __future__ import annotations

import pytest

from actions import builtin
from actions.executor import RegistryExecutor
from interfaces import Action, Screenshot

SHOT = Screenshot(b"", 1280, 720, 0, 0, 2560, 1440)


class FakeGui:
    KEYBOARD_KEYS = ["enter", "tab", "esc", "ctrl", "alt", "shift", "win", "r", "v", "l",
                     "left", "right", "up", "down", "pagedown", "pageup", "delete", "f5"]

    def __init__(self):
        self.calls: list = []

    def press(self, key):
        self.calls.append(("press", key))

    def hotkey(self, *keys):
        self.calls.append(("hotkey", *keys))

    def scroll(self, n):
        self.calls.append(("scroll", n))

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def write(self, text, interval=0.0):
        self.calls.append(("write", text))


class FakeClip:
    def __init__(self, content="user clipboard"):
        self.content = content
        self.history: list[str] = []

    def paste(self):
        return self.content

    def copy(self, text):
        self.history.append(text)
        self.content = text


@pytest.fixture()
def env(monkeypatch):
    gui, clip, opened = FakeGui(), FakeClip(), []
    monkeypatch.setattr(builtin, "_gui", lambda: gui)
    monkeypatch.setattr(builtin, "_clip", lambda: clip)
    monkeypatch.setattr(builtin, "_sleep", lambda s: None)
    monkeypatch.setattr(builtin.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.delenv("ACCEX_DRY_RUN", raising=False)
    monkeypatch.delenv("ACCEX_DEMO", raising=False)
    return gui, clip, opened, RegistryExecutor()


def run(ex, type_, **params):
    return ex.execute(Action(type_, params), SHOT)


def test_catalog():
    names = {s.name: s for s in RegistryExecutor().specs()}
    assert set(names) == {"open_url", "open_app", "scroll", "press_key", "type_text",
                          "click", "email_reply"}
    assert [n for n, s in names.items() if s.dangerous] == ["email_reply"]


def test_open_url(env):
    _, _, opened, ex = env
    r = run(ex, "open_url", url="https://www.youtube.com")
    assert r.ok and r.message == "Opening youtube.com." and opened == ["https://www.youtube.com"]


def test_open_url_adds_scheme(env):
    _, _, opened, ex = env
    assert run(ex, "open_url", url="example.com").ok
    assert opened == ["https://example.com"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///C:/x", "hello"])
def test_open_url_rejects(env, url):
    _, _, opened, ex = env
    assert not run(ex, "open_url", url=url).ok and opened == []


def test_open_app_known(env, monkeypatch):
    gui, _, _, ex = env
    started = []
    monkeypatch.setattr(builtin, "_start", started.append)
    monkeypatch.setattr(builtin.shutil, "which", lambda t: rf"C:\Windows\{t}")
    r = run(ex, "open_app", name="Open Notepad")
    assert r == r.__class__(True, "Opening notepad.")
    assert started == [r"C:\Windows\notepad.exe"] and gui.calls == []


def test_open_app_url_target(env):
    _, _, opened, ex = env
    assert run(ex, "open_app", name="gmail").ok and opened == ["https://mail.google.com"]


def test_open_app_fallback_start_menu(env):
    gui, _, _, ex = env
    r = run(ex, "open_app", name="Visual Studio Code")
    assert r.ok
    assert gui.calls == [("press", "win"), ("write", "visual studio code"), ("press", "enter")]


def test_open_app_known_but_missing_falls_back(env, monkeypatch):
    gui, _, _, ex = env

    def fail(target):
        raise OSError("not found")

    monkeypatch.setattr(builtin, "_start", fail)
    assert run(ex, "open_app", name="word").ok
    assert gui.calls[0] == ("press", "win")


def test_open_app_demo_paths(env, monkeypatch, tmp_path):
    _, _, _, ex = env
    exe = tmp_path / "chrome.exe"
    exe.write_text("")
    monkeypatch.setitem(builtin.DEMO_PATHS, "chrome.exe", [str(exe)])
    monkeypatch.setenv("ACCEX_DEMO", "1")
    monkeypatch.setattr(builtin.shutil, "which", lambda t: r"C:\elsewhere\chrome.exe")
    started = []
    monkeypatch.setattr(builtin, "_start", started.append)
    assert run(ex, "open_app", name="chrome").ok and started == [str(exe)]


def test_scroll(env):
    gui, _, _, ex = env
    assert run(ex, "scroll", direction="down", amount=3).message == "Scrolled down."
    assert run(ex, "scroll", direction="UP").ok
    assert gui.calls == [("scroll", -360), ("scroll", 600)]


def test_scroll_bad_direction(env):
    gui, _, _, ex = env
    assert not run(ex, "scroll", direction="sideways").ok and gui.calls == []


def test_press_key(env):
    gui, _, _, ex = env
    assert run(ex, "press_key", keys="Enter").message == "Pressed enter."
    assert run(ex, "press_key", keys="Control + Return").ok
    assert run(ex, "press_key", keys="alt-left").ok
    assert gui.calls == [("press", "enter"), ("hotkey", "ctrl", "enter"), ("hotkey", "alt", "left")]


def test_press_unknown_key(env):
    gui, _, _, ex = env
    r = run(ex, "press_key", keys="hyperspace")
    assert not r.ok and "hyperspace" in r.message and gui.calls == []


def test_type_text_pastes_and_restores_clipboard(env):
    gui, clip, _, ex = env
    assert run(ex, "type_text", text="Olá, ¿qué tal? ✓").ok
    assert clip.history == ["Olá, ¿qué tal? ✓", "user clipboard"]
    assert clip.content == "user clipboard"
    assert gui.calls == [("hotkey", "ctrl", "v")]


def test_click_scaled(env):
    gui, _, _, ex = env
    r = run(ex, "click", x=100, y=50, target="Compose button")
    assert r.message == "Clicked Compose button." and gui.calls == [("click", 200, 100)]


def test_click_coords_as_strings(env):
    gui, _, _, ex = env
    assert run(ex, "click", x="640", y="360.4").ok and gui.calls == [("click", 1280, 720)]


def test_email_reply_sequence(env):
    gui, clip, _, ex = env
    r = run(ex, "email_reply", body="Thanks Maria, I'll review it tomorrow.")
    assert r.ok and r.message == "Email sent."
    assert gui.calls == [("press", "r"), ("hotkey", "ctrl", "v"), ("hotkey", "ctrl", "enter")]
    assert clip.history[0] == "Thanks Maria, I'll review it tomorrow."


def test_email_reply_empty_body(env):
    gui, _, _, ex = env
    assert not run(ex, "email_reply", body="   ").ok and gui.calls == []


def test_dry_run_touches_nothing(env, monkeypatch):
    gui, clip, opened, ex = env
    monkeypatch.setenv("ACCEX_DRY_RUN", "1")
    for type_, params in [("open_url", {"url": "https://x.com"}), ("click", {"x": 1, "y": 1}),
                          ("email_reply", {"body": "hi"}), ("type_text", {"text": "hi"})]:
        assert ex.execute(Action(type_, params), SHOT).ok
    assert gui.calls == [] and clip.history == [] and opened == []
