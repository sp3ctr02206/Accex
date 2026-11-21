"""Registry + executor validation (no GUI libraries needed)."""
from __future__ import annotations

import pytest

from actions.executor import RegistryExecutor
from actions.registry import action
from interfaces import AccexError, Action, ActionResult, Screenshot

SHOT = Screenshot(b"", 1280, 720, 0, 0, 1920, 1080)


@pytest.fixture()
def reg():
    registry: dict = {}
    calls: list = []

    @action("greet", "Say hi.", {"name": "who", "times": "int"}, registry=registry)
    def greet(name: str, times: int = 1) -> str:
        calls.append(("greet", name, times))
        return f"Hi {name} x{times}."

    @action("poke", "Click.", {"x": "int", "y": "int"}, coords=True, registry=registry)
    def poke(x: int, y: int) -> str:
        calls.append(("poke", x, y))
        return "Poked."

    @action("boom", "Fails.", {}, registry=registry)
    def boom() -> str:
        raise RuntimeError("kaboom")

    @action("refuse", "Expected failure.", {}, registry=registry)
    def refuse() -> str:
        raise AccexError("I can't do that right now.", "detail")

    @action("silent", "Returns nothing.", {}, registry=registry)
    def silent() -> None:
        calls.append(("silent",))

    @action("result", "Returns a result.", {}, registry=registry)
    def result() -> ActionResult:
        return ActionResult(False, "Custom failure.")

    return registry, calls


@pytest.fixture(autouse=True)
def no_dry_run(monkeypatch):
    monkeypatch.delenv("ACCEX_DRY_RUN", raising=False)


def test_specs_from_registry(reg):
    registry, _ = reg
    names = [s.name for s in RegistryExecutor(registry).specs()]
    assert names == ["greet", "poke", "boom", "refuse", "silent", "result"]


def test_runs_and_coerces(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("greet", {"name": "Ana", "times": "3"}), None)
    assert r == ActionResult(True, "Hi Ana x3.")
    assert calls == [("greet", "Ana", 3)]


def test_float_int_from_model(reg):
    registry, calls = reg
    RegistryExecutor(registry).execute(Action("greet", {"name": "A", "times": 2.0}), None)
    assert calls[-1] == ("greet", "A", 2)


def test_unknown_action(reg):
    registry, _ = reg
    r = RegistryExecutor(registry).execute(Action("fly_away", {}), None)
    assert r == ActionResult(False, "I don't know how to fly away.")


def test_missing_required_param(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("greet", {}), None)
    assert not r.ok and r.message == "I need the name to greet."
    assert calls == []


def test_empty_required_param(reg):
    registry, _ = reg
    r = RegistryExecutor(registry).execute(Action("greet", {"name": ""}), None)
    assert not r.ok


def test_invalid_type(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("greet", {"name": "A", "times": "lots"}), None)
    assert not r.ok and "invalid times" in r.message
    assert calls == []


def test_params_not_a_dict(reg):
    registry, _ = reg
    r = RegistryExecutor(registry).execute(Action("greet", ["Ana"]), None)  # type: ignore[arg-type]
    assert not r.ok


def test_unknown_params_ignored(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("greet", {"name": "A", "color": "red"}), None)
    assert r.ok and calls == [("greet", "A", 1)]


def test_coords_scaled(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("poke", {"x": 640, "y": 360}), SHOT)
    assert r.ok and calls == [("poke", 960, 540)]


def test_coords_need_screenshot(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("poke", {"x": 1, "y": 1}), None)
    assert not r.ok and "couldn't see the screen" in r.message and calls == []


def test_coords_out_of_bounds(reg):
    registry, calls = reg
    r = RegistryExecutor(registry).execute(Action("poke", {"x": 5000, "y": 1}), SHOT)
    assert not r.ok and calls == []


def test_exception_becomes_speakable(reg):
    registry, _ = reg
    r = RegistryExecutor(registry).execute(Action("boom", {}), None)
    assert r == ActionResult(False, "Sorry, I couldn't boom.")


def test_accex_error_spoken(reg):
    registry, _ = reg
    r = RegistryExecutor(registry).execute(Action("refuse", {}), None)
    assert r == ActionResult(False, "I can't do that right now.")


def test_failsafe_message(reg):
    registry = reg[0]

    class FailSafeException(Exception):
        pass

    @action("corner", "", {}, registry=registry)
    def corner() -> str:
        raise FailSafeException()

    r = RegistryExecutor(registry).execute(Action("corner", {}), None)
    assert not r.ok and "corner" in r.message


def test_none_return_is_done(reg):
    registry, _ = reg
    assert RegistryExecutor(registry).execute(Action("silent"), None) == ActionResult(True, "Done.")


def test_action_result_passthrough(reg):
    registry, _ = reg
    assert RegistryExecutor(registry).execute(Action("result"), None) == \
        ActionResult(False, "Custom failure.")


def test_dry_run_does_not_act(reg, monkeypatch):
    registry, calls = reg
    monkeypatch.setenv("ACCEX_DRY_RUN", "1")
    r = RegistryExecutor(registry).execute(Action("greet", {"name": "A"}), None)
    assert r.ok and r.message.startswith("Dry run") and calls == []


def test_dry_run_still_validates(reg, monkeypatch):
    registry, _ = reg
    monkeypatch.setenv("ACCEX_DRY_RUN", "1")
    assert not RegistryExecutor(registry).execute(Action("greet", {}), None).ok


def test_decorator_rejects_mismatched_params():
    with pytest.raises(ValueError):
        @action("bad", "", {"a": "x"}, registry={})
        def bad(b: str) -> str:
            return ""


def test_decorator_rejects_duplicates():
    registry: dict = {}
    action("dup", "", {}, registry=registry)(lambda: "")
    with pytest.raises(ValueError):
        action("dup", "", {}, registry=registry)(lambda: "")
