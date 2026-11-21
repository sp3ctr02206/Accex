"""Action executor (owner: P3). Implements interfaces.ActionExecutor.

execute() validates the action type and params, coerces values to the declared
types, maps click coordinates from image pixels to screen pixels, and turns every
exception into ActionResult(ok=False, <speakable message>). It never raises.

ACCEX_DRY_RUN=1 -> actions are only printed, nothing touches the computer.
ACCEX_DEMO=1    -> every action and its outcome is printed to the console.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

from interfaces import AccexError, Action, ActionResult, ActionSpec, Screenshot

from .registry import REGISTRY, RegisteredAction

_TRUE = {"true", "yes", "1", "on"}
_FALSE = {"false", "no", "0", "off"}


def _spoken_name(action_type: str) -> str:
    return action_type.replace("_", " ")


def _coerce(value: Any, kind: type) -> Any:
    if kind is bool:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError(f"not a boolean: {value!r}")
    if kind is int:
        if isinstance(value, bool):
            raise ValueError("bool is not an int")
        return int(round(float(value)))   # the model sometimes sends 412.0 or "412"
    if kind is float:
        return float(value)
    if kind is str:
        if value is None or isinstance(value, (dict, list)):
            raise ValueError(f"not text: {value!r}")
        return str(value)
    return value


class RegistryExecutor:
    def __init__(self, registry: dict[str, RegisteredAction] | None = None) -> None:
        if registry is None:
            from . import builtin  # noqa: F401  (importing registers the built-in actions)
            registry = REGISTRY
        self.registry = registry

    @property
    def dry_run(self) -> bool:
        return os.getenv("ACCEX_DRY_RUN", "0") == "1"

    @property
    def verbose(self) -> bool:
        return os.getenv("ACCEX_DEMO", "0") == "1"

    def specs(self) -> list[ActionSpec]:
        return [entry.spec for entry in self.registry.values()]

    # ------------------------------------------------------------ execute
    def execute(self, action: Action, screenshot: Screenshot | None) -> ActionResult:
        t0 = time.perf_counter()
        try:
            result = self._execute(action, screenshot)
        except AccexError as e:
            result = ActionResult(False, e.spoken)
            self._print(f"{action.type} failed: {e}")
        except Exception as e:  # includes pyautogui.FailSafeException
            result = ActionResult(False, self._crash_message(action, e))
            self._print(f"{action.type} crashed: {e!r}")
        ms = round((time.perf_counter() - t0) * 1000)
        self._print(f"{action.type} -> ok={result.ok} {result.message!r} ({ms} ms)")
        return result

    def _execute(self, action: Action, screenshot: Screenshot | None) -> ActionResult:
        entry = self.registry.get(action.type)
        if entry is None:
            return ActionResult(False, f"I don't know how to {_spoken_name(action.type)}.")
        kwargs = self._validate(entry, action.params)
        if entry.coords:
            kwargs["x"], kwargs["y"] = self._to_screen(kwargs["x"], kwargs["y"], screenshot)

        if self.dry_run:
            print(f"[DRY RUN] {action.type} {kwargs}", file=sys.stderr)
            return ActionResult(True, f"Dry run: I would {_spoken_name(action.type)}.")

        self._print(f"running {action.type} {kwargs}")
        out = entry.func(**kwargs)
        if isinstance(out, ActionResult):
            return out
        return ActionResult(True, str(out) if out else "Done.")

    def _validate(self, entry: RegisteredAction, params: dict[str, Any] | None) -> dict[str, Any]:
        if params is not None and not isinstance(params, dict):
            raise AccexError(f"I got the wrong details for {_spoken_name(entry.spec.name)}.",
                             f"params is {type(params).__name__}, not dict")
        params = dict(params or {})
        unknown = set(params) - set(entry.spec.params)
        if unknown:
            self._print(f"ignoring unknown params for {entry.spec.name}: {sorted(unknown)}")
        kwargs: dict[str, Any] = {}
        for name in entry.spec.params:
            if name not in params or params[name] is None or params[name] == "":
                if name in entry.required:
                    raise AccexError(
                        f"I need the {name.replace('_', ' ')} to {_spoken_name(entry.spec.name)}.",
                        f"missing param {name!r}")
                continue
            value = params[name]
            kind = entry.types.get(name)
            if kind is not None:
                try:
                    value = _coerce(value, kind)
                except (TypeError, ValueError) as e:
                    raise AccexError(
                        f"I got an invalid {name.replace('_', ' ')} for "
                        f"{_spoken_name(entry.spec.name)}.", f"{name}={params[name]!r}: {e}")
            kwargs[name] = value
        return kwargs

    @staticmethod
    def _to_screen(x: float, y: float, screenshot: Screenshot | None) -> tuple[int, int]:
        if screenshot is None or not screenshot.width or not screenshot.height:
            raise AccexError("I can't click there because I couldn't see the screen.",
                             "no screenshot to map coordinates")
        if not (0 <= x <= screenshot.width and 0 <= y <= screenshot.height):
            raise AccexError("That spot is outside the screen.",
                             f"({x}, {y}) outside {screenshot.width}x{screenshot.height}")
        return screenshot.to_screen(x, y)

    @staticmethod
    def _crash_message(action: Action, e: Exception) -> str:
        if type(e).__name__ == "FailSafeException":
            return "I stopped because the mouse was moved to a corner of the screen."
        return f"Sorry, I couldn't {_spoken_name(action.type)}."

    def _print(self, text: str) -> None:
        if self.verbose:
            print(f"[ACTIONS] {text}", file=sys.stderr)
