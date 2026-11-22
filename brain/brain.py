"""Vision brain (owner: P2). Implements interfaces.Brain.

Memory is text only: the last ACCEX_HISTORY_TURNS question/answer pairs. Only the newest
screenshot is sent. Results of executed or cancelled actions are noted and prepended to
the next question, so assistant turns in the history stay pure JSON.
"""
from __future__ import annotations

import json
import os

from interfaces import Action, ActionResult, ActionSpec, LLMResponse, Screenshot

from .parse import parse_llm_reply
from .prompt import build_system_prompt, build_user_text
from .providers import VisionProvider, create_provider


def _compact_json(resp: LLMResponse) -> str:
    action = resp.action and {"type": resp.action.type, "params": resp.action.params}
    return json.dumps({"say": resp.say, "action": action,
                       "needs_confirmation": resp.needs_confirmation}, ensure_ascii=False)


class VisionBrain:
    def __init__(self, specs: list[ActionSpec], provider: VisionProvider | None = None,
                 history_turns: int | None = None) -> None:
        self.system = build_system_prompt(specs)
        self.provider = provider or create_provider()
        self.max_turns = history_turns or int(os.getenv("ACCEX_HISTORY_TURNS", "12"))
        self.turns: list[tuple[str, str]] = []   # (question text sent, assistant JSON)
        self.notes: list[str] = []
        self.senior = None                       # ACCEX_PROFILE=senior only (brain/senior.py)
        if os.getenv("ACCEX_PROFILE", "default").strip().lower() == "senior":
            from .senior import SeniorMode
            self.senior = SeniorMode.from_env()
            self.system += self.senior.prompt_block()

    def ask(self, question: str, screenshot: Screenshot | None) -> LLMResponse:
        user_text = build_user_text(question, screenshot, self.notes)
        history = [msg for q, a in self.turns for msg in (("user", q), ("assistant", a))]
        raw = self.provider.complete(self.system, history, user_text, screenshot)  # AccexError
        resp = parse_llm_reply(raw)
        if self.senior is not None:
            resp = self.senior.apply(resp, question)
        past_text = build_user_text(question, None, self.notes, for_history=True)
        self.notes.clear()
        self.turns.append((past_text, _compact_json(resp)))
        del self.turns[:-self.max_turns]
        return resp

    def record_action(self, action: Action, result: ActionResult) -> None:
        status = "done" if result.ok else "not done"
        self.notes.append(f"Result of your last action {action.type}: {status}. {result.message}")
        if self.senior is not None:
            self.senior.on_action(action, result)

    def reset(self) -> None:
        self.turns.clear()
        self.notes.clear()
