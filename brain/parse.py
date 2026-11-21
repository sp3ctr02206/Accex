"""Tolerant parsing of the model's reply into an LLMResponse (owner: P2). Never raises."""
from __future__ import annotations

import json
import re
from typing import Any

from interfaces import Action, LLMResponse

EMPTY_REPLY = "Sorry, I didn't get an answer. Please try again."
MAX_FALLBACK_CHARS = 400

_decoder = json.JSONDecoder()


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Return the first JSON object in text that has a "say" or "action" key."""
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = _decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and ("say" in obj or "action" in obj):
            return obj
    return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _as_action(value: Any) -> Action | None:
    if not isinstance(value, dict):
        return None
    kind = value.get("type") or value.get("name")
    if not isinstance(kind, str) or not kind.strip():
        return None
    params = value.get("params")
    if not isinstance(params, dict):  # tolerate {"type": "open_url", "url": "..."}
        params = {k: v for k, v in value.items() if k not in {"type", "name", "params"}}
    return Action(type=kind.strip(), params=params)


def _plain_text(text: str) -> str:
    """Fallback when there is no JSON: speak the text itself, without code fences."""
    text = re.sub(r"```[a-zA-Z]*", "", text).strip()
    if len(text) > MAX_FALLBACK_CHARS:
        text = text[:MAX_FALLBACK_CHARS].rsplit(" ", 1)[0] + "..."
    return text or EMPTY_REPLY


def parse_llm_reply(text: str) -> LLMResponse:
    raw = text or ""
    obj = _first_json_object(raw)
    if obj is None:
        return LLMResponse(say=_plain_text(raw), raw=raw)

    say = obj.get("say")
    say = say.strip() if isinstance(say, str) else ""
    action = _as_action(obj.get("action"))
    if not say and action is None:
        say = EMPTY_REPLY
    return LLMResponse(say=say, action=action,
                       needs_confirmation=_as_bool(obj.get("needs_confirmation", False)),
                       raw=raw)
