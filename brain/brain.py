"""Vision brain (owner: P2). Implements interfaces.Brain.

TODO(P2), see PLAN.md > Person 2:
- providers.py: AnthropicVision (default, ACCEX_LLM_MODEL / ACCEX_LLM_EFFORT, check
  stop_reason == "refusal", server-side fallbacks) and OpenAIVision.
- parse.py: tolerant JSON -> LLMResponse; fall back to say-only, never raise.
- Memory: last ACCEX_HISTORY_TURNS text turns + action notes; only the newest
  screenshot is sent.
- API/network errors -> AccexError("I couldn't reach the AI service. Please try again.").
"""
from __future__ import annotations

from interfaces import Action, ActionResult, ActionSpec, LLMResponse, Screenshot


class VisionBrain:
    def __init__(self, specs: list[ActionSpec]) -> None:
        raise NotImplementedError("brain.VisionBrain (P2) - run with --mock brain")

    def ask(self, question: str, screenshot: Screenshot | None) -> LLMResponse:
        raise NotImplementedError

    def record_action(self, action: Action, result: ActionResult) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError
