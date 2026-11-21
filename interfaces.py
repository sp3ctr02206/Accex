"""Accex shared contract. FROZEN: change only with agreement of all 3 owners.

Ownership:  voice/   (P1): Listener, SpeechToText, Speaker
            brain/   (P2): ScreenCapturer, Brain  (+ main.py orchestration)
            actions/ (P3): ActionExecutor, ConfirmationGate;  demo/ (P3): EventLog

Factory convention -- each package AND its mock in mocks/ expose the same factories,
so main.py can swap real <-> mock per package. Config comes only from env (.env).
    voice.create_listener() -> Listener        voice.create_stt() -> SpeechToText
    voice.create_speaker() -> Speaker          brain.create_capturer() -> ScreenCapturer
    brain.create_brain(specs: list[ActionSpec]) -> Brain
    actions.create_executor() -> ActionExecutor   actions.create_gate() -> ConfirmationGate
    demo.create_log() -> EventLog
Privacy: screenshots and audio live in memory only; nothing here is ever written to disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol


class AccexError(Exception):
    """Expected failure carrying a message that is safe to speak to the user.

    Modules raise this instead of leaking library exceptions. main.py catches it,
    speaks `.spoken`, and logs str(e) (technical detail).
    """

    def __init__(self, spoken: str, detail: str = "") -> None:
        super().__init__(detail or spoken)
        self.spoken = spoken


# ------------------------------------------------------------------ data types
@dataclass(frozen=True)
class AudioClip:
    """One push-to-talk recording: a complete WAV file (16 kHz, mono, 16-bit PCM)."""
    wav_bytes: bytes
    duration_s: float


@dataclass(frozen=True)
class Screenshot:
    """Downscaled JPEG of the primary monitor plus the geometry needed to map clicks back."""
    jpeg_bytes: bytes
    width: int            # size of the image the model sees
    height: int
    screen_left: int      # physical-pixel geometry of the captured monitor
    screen_top: int
    screen_width: int
    screen_height: int

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        """Map a point in image pixels (model space) to physical screen pixels."""
        return (self.screen_left + round(x * self.screen_width / self.width),
                self.screen_top + round(y * self.screen_height / self.height))


@dataclass(frozen=True)
class Action:
    """An action requested by the model. `type` must match a registered ActionSpec.name.
    Coordinates in params (e.g. click x/y) are in Screenshot image pixels."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Parsed model reply. Wire format the model must ALWAYS return:
    {"say": "<1-3 short sentences>", "action": null | {"type": str, "params": {}},
     "needs_confirmation": bool}"""
    say: str
    action: Action | None = None
    needs_confirmation: bool = False
    raw: str = ""         # unparsed model text, for logs only


@dataclass(frozen=True)
class ActionSpec:
    """One registered action; rendered into the system prompt's action catalog."""
    name: str
    description: str
    params: dict[str, str]        # param name -> description (type, format, example)
    dangerous: bool = False       # True = always needs spoken confirmation


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str                  # short and speakable, e.g. "I couldn't find that button."


Confirmation = Literal["yes", "no", "unclear"]
Cue = Literal["listening", "thinking", "done", "error"]


# ------------------------------------------------------------------ voice (P1)
class Listener(Protocol):
    def wait_for_utterance(self, on_start: Callable[[], None] | None = None) -> AudioClip:
        """Block until the push-to-talk key is pressed AND released; return the recording.

        on_start() is called on the CALLER's thread as soon as the key goes down (main uses
        it to stop speech and start the screenshot). Taps shorter than ~0.3 s still call
        on_start but are not returned; the listener keeps waiting. Raises AccexError if
        the microphone cannot be opened."""
        ...


class SpeechToText(Protocol):
    def transcribe(self, clip: AudioClip) -> str:
        """Return the English transcript, '' if nothing intelligible. AccexError on API failure."""
        ...


class Speaker(Protocol):
    def say(self, text: str) -> None:
        """Start speaking and return immediately; interrupts anything already playing."""
        ...

    def stop(self) -> None:
        """Silence speech immediately (barge-in)."""
        ...

    def wait(self, timeout: float | None = None) -> None:
        """Block until current speech has finished (or timeout)."""
        ...

    def cue(self, name: Cue) -> None:
        """Play a short non-verbal sound, non-blocking."""
        ...


# ------------------------------------------------------------------ brain (P2)
class ScreenCapturer(Protocol):
    def capture(self) -> Screenshot:
        """Capture the primary monitor now. AccexError on failure."""
        ...


class Brain(Protocol):
    def ask(self, question: str, screenshot: Screenshot | None) -> LLMResponse:
        """System prompt + last N turns + question + screenshot -> parsed reply; stores the turn.
        Malformed JSON never raises (falls back to say-only). AccexError on network/API failure."""
        ...

    def record_action(self, action: Action, result: ActionResult) -> None:
        """Append the outcome of an executed or cancelled action to memory."""
        ...

    def reset(self) -> None:
        """Forget the conversation."""
        ...


# ------------------------------------------------------------------ actions + demo (P3)
class ActionExecutor(Protocol):
    def specs(self) -> list[ActionSpec]:
        """All registered actions (fed to the Brain's system prompt)."""
        ...

    def execute(self, action: Action, screenshot: Screenshot | None) -> ActionResult:
        """Validate params and run. NEVER raises: failures return ok=False + speakable message."""
        ...


class ConfirmationGate(Protocol):
    def requires_confirmation(self, action: Action, model_flag: bool) -> bool:
        """True if model_flag is set OR the action's spec is dangerous (injection defense)."""
        ...

    def classify(self, reply: str) -> Confirmation:
        """Map a spoken reply to yes/no/unclear. Pure keyword logic, no LLM call."""
        ...


class EventLog(Protocol):
    def log(self, event: str, **data: Any) -> None:
        """Record one event; never raises; never stores images or audio.
        Standard events: transcript(text, ms) llm(raw, ms) say(text) action(type, params)
        action_result(ok, message, ms) confirm(reply, verdict) error(where, detail)
        latency(stt_ms, capture_ms, llm_ms, total_ms)."""
        ...
