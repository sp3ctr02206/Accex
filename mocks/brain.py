"""Mock brain (owner: P2). Keyword rules that cover the demo script, no API calls."""
from __future__ import annotations

from interfaces import Action, ActionResult, ActionSpec, LLMResponse, Screenshot


class StaticCapturer:
    """Returns an empty 1280x720 'image' of a 1920x1080 screen."""

    def capture(self) -> Screenshot:
        return Screenshot(jpeg_bytes=b"", width=1280, height=720,
                          screen_left=0, screen_top=0, screen_width=1920, screen_height=1080)


REPLY_BODY = "Thanks Maria, I'll review it tomorrow."


class ScriptedBrain:
    """Answers the demo questions; keeps a text history like the real brain."""

    def __init__(self, specs: list[ActionSpec]) -> None:
        self.specs = specs
        self.history: list[tuple[str, str]] = []
        self.plan: list[LLMResponse] = []      # remaining steps of a multi-step task
        self.final = ""                        # what to say when the plan is done
        self.last_result: ActionResult | None = None

    def ask(self, question: str, screenshot: Screenshot | None) -> LLMResponse:
        q = question.strip().lower()
        resp = self._continue() if q == "[continue]" else self._answer(q)
        self.history.append(("user", question))
        self.history.append(("assistant", resp.say))
        return resp

    def _continue(self) -> LLMResponse:
        """Next step of the current task, or a confirmation of the last action's result."""
        if self.plan:
            return self.plan.pop(0)
        final, self.final = self.final, ""
        if final:
            return LLMResponse(say=final)
        return LLMResponse(say=self.last_result.message if self.last_result else "Done.")

    def _answer(self, q: str) -> LLMResponse:
        self.plan, self.final = [], ""
        if "spotify" in q and "play" in q:
            self.plan = [
                LLMResponse(say="Clicking search.",
                            action=Action("click", {"x": 600, "y": 30, "target": "Search"})),
                LLMResponse(say="Typing the song.",
                            action=Action("type_text", {"text": "Money for Nothing"})),
                LLMResponse(say="Searching.", action=Action("press_key", {"keys": "enter"})),
            ]
            self.final = "Money for Nothing by Dire Straits is playing."
            return LLMResponse(say="Opening Spotify.",
                               action=Action("open_app", {"name": "spotify"}))
        if "reply" in q:
            return LLMResponse(
                say=f"I'll reply: '{REPLY_BODY}' Do you want me to send it?",
                action=Action("email_reply", {"body": REPLY_BODY}),
                needs_confirmation=True)
        if "email" in q or "mail" in q:
            return LLMResponse(say="Your latest email is from Maria Lopez, subject Q3 report. "
                                   "She asks you to review the attached report before Friday.")
        if "highest" in q:
            return LLMResponse(say="March had the highest sales, about 142 thousand dollars.")
        if "lowest" in q:
            return LLMResponse(say="August had the lowest sales, about 61 thousand dollars.")
        if "screen" in q:
            return LLMResponse(say="This is a sales dashboard for 2026 with a bar chart of "
                                   "monthly sales. Total sales are 1.24 million dollars.")
        if "open" in q and "youtube" in q:
            return LLMResponse(say="Opening YouTube.",
                               action=Action("open_url", {"url": "https://www.youtube.com"}))
        if "scroll" in q:
            direction = "up" if "up" in q else "down"
            return LLMResponse(say=f"Scrolling {direction}.",
                               action=Action("scroll", {"direction": direction, "amount": 5}))
        return LLMResponse(say="I'm the mock brain. I only know the demo questions.")

    def record_action(self, action: Action, result: ActionResult) -> None:
        self.last_result = result
        self.history.append(("assistant", f"[action {action.type}: {result.message}]"))

    def reset(self) -> None:
        self.history.clear()
        self.plan, self.final, self.last_result = [], "", None


def create_capturer() -> StaticCapturer:
    return StaticCapturer()


def create_brain(specs: list[ActionSpec]) -> ScriptedBrain:
    return ScriptedBrain(specs)
