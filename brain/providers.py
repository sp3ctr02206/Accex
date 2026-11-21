"""Vision LLM providers (owner: P2).

Every provider has one method:
    complete(system, history, user_text, screenshot) -> str
where history is a list of ("user" | "assistant", text) pairs, oldest first, and the
screenshot (if any) is attached to the new user message only. Providers turn every
library error into an AccexError with a speakable message.
"""
from __future__ import annotations

import base64
import os
from typing import Protocol

from interfaces import AccexError, Screenshot

History = list[tuple[str, str]]

MAX_TOKENS = 8000  # includes thinking; replies themselves are short


def _timeout() -> float:
    return float(os.getenv("ACCEX_LLM_TIMEOUT", "20"))

# Models that accept the server-side refusal fallback ("default" routing).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
                    "claude-fable-5-2", "claude-fable-5-1"}


class VisionProvider(Protocol):
    model: str

    def complete(self, system: str, history: History, user_text: str,
                 screenshot: Screenshot | None) -> str: ...


def _b64(screenshot: Screenshot) -> str:
    return base64.standard_b64encode(screenshot.jpeg_bytes).decode("ascii")


class AnthropicVision:
    def __init__(self, model: str | None = None, effort: str | None = None) -> None:
        import anthropic
        self._anthropic = anthropic
        self.model = model or os.getenv("ACCEX_LLM_MODEL", "claude-opus-5-5")
        self.effort = effort or os.getenv("ACCEX_LLM_EFFORT", "low")
        self.client = anthropic.Anthropic(timeout=_timeout(), max_retries=1)
        self.use_fallbacks = (self.model in _FALLBACK_MODELS
                              and os.getenv("ACCEX_LLM_FALLBACKS", "1") == "1")

    def complete(self, system: str, history: History, user_text: str,
                 screenshot: Screenshot | None) -> str:
        a = self._anthropic
        content: list[dict] = []
        if screenshot is not None and screenshot.jpeg_bytes:
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": _b64(screenshot)}})
        content.append({"type": "text", "text": user_text})
        messages = [{"role": r, "content": t} for r, t in history]
        messages.append({"role": "user", "content": content})

        kwargs = dict(model=self.model, max_tokens=MAX_TOKENS, system=system,
                      messages=messages, output_config={"effort": self.effort})
        try:
            if self.use_fallbacks:
                resp = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
            else:
                resp = self.client.messages.create(**kwargs)
        except a.APITimeoutError as e:
            raise AccexError("The AI service is taking too long. Please try again.", repr(e)) from e
        except a.APIConnectionError as e:
            raise AccexError("I can't reach the internet right now.", repr(e)) from e
        except a.AuthenticationError as e:
            raise AccexError("My AI key isn't working. Please check the setup.", repr(e)) from e
        except a.RateLimitError as e:
            raise AccexError("The AI service is busy. Please try again in a moment.", repr(e)) from e
        except a.APIStatusError as e:
            raise AccexError("I couldn't reach the AI service. Please try again.",
                             f"{e.status_code}: {e.message}") from e
        except a.AnthropicError as e:
            raise AccexError("I couldn't reach the AI service. Please check the setup.",
                             repr(e)) from e
        except TypeError as e:  # the SDK raises TypeError when no credentials are configured
            if "authentication" not in str(e):
                raise
            raise AccexError("My AI key isn't set up. Please check the setup.", repr(e)) from e

        if resp.stop_reason == "refusal":
            raise AccexError("Sorry, I can't help with that one.",
                             f"refusal: {getattr(resp, 'stop_details', None)}")
        return "".join(b.text for b in resp.content if b.type == "text")


class OpenAIVision:
    def __init__(self, model: str | None = None) -> None:
        import openai
        self._openai = openai
        self.model = model or os.getenv("ACCEX_LLM_MODEL", "")
        if not self.model or self.model.startswith("claude"):
            raise AccexError("The AI model isn't configured.",
                             "ACCEX_LLM_PROVIDER=openai needs an OpenAI ACCEX_LLM_MODEL")
        self.client = openai.OpenAI(timeout=_timeout(), max_retries=1)

    def complete(self, system: str, history: History, user_text: str,
                 screenshot: Screenshot | None) -> str:
        o = self._openai
        content: list[dict] = [{"type": "text", "text": user_text}]
        if screenshot is not None and screenshot.jpeg_bytes:
            content.insert(0, {"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{_b64(screenshot)}"}})
        messages = [{"role": "system", "content": system}]
        messages += [{"role": r, "content": t} for r, t in history]
        messages.append({"role": "user", "content": content})
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages,
                response_format={"type": "json_object"})
        except o.APITimeoutError as e:
            raise AccexError("The AI service is taking too long. Please try again.", repr(e)) from e
        except o.APIConnectionError as e:
            raise AccexError("I can't reach the internet right now.", repr(e)) from e
        except o.OpenAIError as e:
            raise AccexError("I couldn't reach the AI service. Please try again.", repr(e)) from e
        return resp.choices[0].message.content or ""


def create_provider() -> VisionProvider:
    name = os.getenv("ACCEX_LLM_PROVIDER", "anthropic").strip().lower()
    if name == "anthropic":
        return AnthropicVision()
    if name == "openai":
        return OpenAIVision()
    raise AccexError("The AI service isn't configured.", f"unknown ACCEX_LLM_PROVIDER={name!r}")
