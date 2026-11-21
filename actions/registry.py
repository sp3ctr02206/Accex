"""Action registry (owner: P3).

Adding an action = writing one decorated function:

    @action("open_url", "Open a web page in the default browser.",
            {"url": "full https URL, e.g. https://www.youtube.com"})
    def open_url(url: str) -> str:
        ...
        return "Opening youtube.com."

- `params` (name -> description) is what the model sees in the action catalog.
- Required params are the function arguments without a default value.
- Annotations int / float / str / bool are used to coerce the model's values.
- `coords=True` means the action takes `x`, `y` in screenshot image pixels; the
  executor maps them to physical screen pixels before calling the function.
- The function returns a short speakable success message (or an ActionResult) and
  raises AccexError(spoken, detail) for expected failures.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from interfaces import ActionSpec


@dataclass(frozen=True)
class RegisteredAction:
    spec: ActionSpec
    func: Callable[..., Any]
    required: tuple[str, ...]
    types: dict[str, type]
    coords: bool = False


REGISTRY: dict[str, RegisteredAction] = {}

_COERCIBLE = {"int": int, "float": float, "str": str, "bool": bool,
              int: int, float: float, str: str, bool: bool}


def action(name: str, description: str, params: dict[str, str] | None = None,
           dangerous: bool = False, coords: bool = False,
           registry: dict[str, RegisteredAction] | None = None) -> Callable:
    """Register the decorated function as an action. `registry` is for tests."""
    target = REGISTRY if registry is None else registry
    params = dict(params or {})

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in target:
            raise ValueError(f"action {name!r} registered twice")
        sig = inspect.signature(func)
        missing = [p for p in sig.parameters if p not in params]
        extra = [p for p in params if p not in sig.parameters]
        if missing or extra:
            raise ValueError(f"action {name!r}: params {params.keys()} don't match "
                             f"function arguments {list(sig.parameters)}")
        required = tuple(p.name for p in sig.parameters.values()
                         if p.default is inspect.Parameter.empty)
        types = {p.name: _COERCIBLE[p.annotation] for p in sig.parameters.values()
                 if p.annotation in _COERCIBLE}
        target[name] = RegisteredAction(
            spec=ActionSpec(name, description, params, dangerous),
            func=func, required=required, types=types, coords=coords)
        return func

    return decorate
