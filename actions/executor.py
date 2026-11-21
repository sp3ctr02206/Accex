"""Action executor (owner: P3). Implements interfaces.ActionExecutor.

TODO(P3), see PLAN.md > Person 3:
- registry.py: @action(name, description, params, dangerous=False) decorator -> REGISTRY.
- builtin.py: open_url, open_app, scroll, press_key, type_text (clipboard paste), click,
  email_reply (dangerous). Adding an action = one decorated function.
- execute(): validate type + params, scale x/y with Screenshot.to_screen, catch every
  exception into ActionResult(ok=False, <speakable message>). ACCEX_DRY_RUN=1 logs only.
"""
from __future__ import annotations

from interfaces import Action, ActionResult, ActionSpec, Screenshot


class RegistryExecutor:
    def __init__(self) -> None:
        raise NotImplementedError("actions.RegistryExecutor (P3) - run with --mock actions")

    def specs(self) -> list[ActionSpec]:
        raise NotImplementedError

    def execute(self, action: Action, screenshot: Screenshot | None) -> ActionResult:
        raise NotImplementedError
