# Accex — team plan

Hand this file to your Claude Code session along with `interfaces.py`, and tell it which person you are.

**Goal:** a reliable live demo. Reliability of the demo path matters more than the number of features.

## Rules for everyone

- Each person works on their own branch and edits **only the files they own**:

  | Person | Branch | Owns |
  |---|---|---|
  | P1 | `p1-voice` | `voice/`, `mocks/voice.py` |
  | P2 | `p2-brain` | `brain/`, `main.py`, `mocks/brain.py`, `tests/test_loop_mocks.py` |
  | P3 | `p3-actions` | `actions/`, `demo/`, `mocks/actions.py`, `mocks/demo.py` |

- **`interfaces.py` is frozen.** Change it only when all three agree, and land the change on `main` first.
- Shared files (`requirements.txt`, `.env.example`, `README.md`) may be edited for your own section only. Keep those edits small to avoid merge conflicts.
- Put your module's tests in `<package>/tests/`. The whole suite must pass with **mocks only**, with no API keys and no hardware.
- Raise `AccexError(spoken, detail)` for expected failures. Never fail silently.
- Never write screenshots or audio to disk.
- Before each checkpoint merge, run on your branch:

  ```
  git merge main
  pytest
  python main.py --mock <the other packages>
  ```

  Then merge into `main`.

## Core loop (implemented in `main.py`, `Assistant`)

1. **Key down:** stop speech, play the listening cue, start the screenshot in the background.
2. **Key up:** play the thinking cue, run STT.
3. **If an action is waiting for confirmation:**
   - "yes" runs it
   - "no" cancels it
   - anything else gets "Please say yes or no."
4. **Otherwise:**
   - Call `brain.ask(text, screenshot)`. If it takes longer than 1.5 s, say "One moment."
   - Speak `say`.
   - If the action needs confirmation, keep it pending. Otherwise execute it now.
5. Every failure is spoken and logged.

---

## 1. Stack (Windows)

| Need | Choice | Pitfalls / mitigation |
|---|---|---|
| Python | 3.12 or 3.13 | Avoid newer versions: some dependencies may lack wheels. |
| Push-to-talk | **pynput**, hold **Right Ctrl** (`ACCEX_HOTKEY`) | Needs no admin. Hooks don't fire in elevated windows. Never use Insert/CapsLock (NVDA modifiers). Ctrl also silences NVDA. |
| Microphone | **sounddevice** 16 kHz mono int16, WAV in memory | Windows mic privacy toggle must be on. `ACCEX_MIC_DEVICE` picks the device. Use a headset mic. |
| STT | OpenAI `gpt-4o-mini-transcribe` (fallback `whisper-1`), `language="en"` | — |
| Capture | **mss** + **Pillow**, longest side ≤1280, JPEG q≈80 | `main.py` sets DPI awareness first, so capture and click coordinates are both physical pixels. |
| Vision LLM | `anthropic` SDK, `claude-haiku-5-5`, effort `low` (`.env`) | Send only the newest screenshot; history is text only. Haiku: p50 0.8 s vs Opus 1.9 s, same accuracy on the dashboard eval. Switch to `claude-opus-5-5` in `.env` if actions need more accuracy. |
| TTS | **SAPI via pywin32** (async + purge = interruptible) | **No pyttsx3**: it blocks, hangs and can't be interrupted. Stretch: OpenAI TTS, or speaking through NVDA's controller client. |
| Earcons | numpy sine tones + `sounddevice.play` | — |
| Actions | `webbrowser`, `os.startfile`, **pyautogui**, **pyperclip** (paste text) | `pyautogui.write` is ASCII-only, so paste instead. Elevated windows can't receive input (UIPI). Keep `FAILSAFE=True`. |

---

## Person 1 — voice

**Files:** `voice/hotkey.py`, `voice/stt.py`, `voice/tts.py`, `voice/cues.py`, `voice/try_voice.py`, `voice/tests/`, `mocks/voice.py`

**Build in this order:**
1. `PushToTalkListener` (`hotkey.py`):
   - The pynput listener thread pushes press/release events into a `queue.Queue`.
   - `wait_for_utterance()` consumes the queue **on the caller's thread** and calls `on_start()` there when the key goes down.
   - A `sounddevice.InputStream` collects frames while the key is held.
   - Build the WAV with the `wave` module into a `BytesIO`.
   - Ignore taps under 0.3 s (they still call `on_start`, so a tap silences speech).
2. `OpenAISTT` (`stt.py`):
   - Send the WAV as an in-memory file, with `language="en"` and a timeout.
   - Raise `AccexError` on failure.
3. `SapiSpeaker` (`tts.py`):
   - Create it on the main thread with `Dispatch("SAPI.SpVoice")`.
   - `say` = `Speak(text, 3)` (async + purge); `stop` = `Speak("", 3)`; `wait` = `WaitUntilDone`.
4. `cue()`: four distinct short tones (listening, thinking, done, error).
5. `try_voice.py`: hold the key, print the transcript and its latency, then speak it back.
6. NVDA test: with NVDA running, PTT must not trigger NVDA commands, and our speech must not overlap with NVDA's.
7. Stretch: `OpenAISpeaker` (streamed), or speaking through NVDA's `nvdaControllerClient.dll`.

**Test alone:** `python main.py --mock brain,actions` lets you talk to the scripted brain. Unit-test the WAV builder and the tap filter.

**Done when:**
- 20 consecutive questions are transcribed correctly in a normal room.
- A tap interrupts speech.
- There is no NVDA conflict.
- Speech starts within 0.3 s of `say()`.

## Person 2 — brain + main loop

**Files:** `brain/capture.py`, `brain/prompt.py`, `brain/parse.py`, `brain/providers.py`, `brain/brain.py`, `brain/try_brain.py`, `brain/tests/`, `main.py`, `mocks/brain.py`, `tests/test_loop_mocks.py`

**Build in this order:**
1. `MssCapturer`: capture the primary monitor (`monitors[1]`), resize, encode as JPEG, and fill in the `Screenshot` geometry.
2. `prompt.py`: render `SYSTEM_PROMPT` with the action catalog built from `ActionSpec`s and the image size.
3. `parse.py`:
   - Strip code fences, take the first `{...}`, and validate `say`, `action` and `needs_confirmation`.
   - Unknown or garbled output → `LLMResponse(say=<text>)`. Never raise.
4. `providers.py`:
   - `AnthropicVision` (default): image block + text, `output_config.effort`, check `stop_reason == "refusal"`, server-side fallbacks.
   - `OpenAIVision` as the alternative.
   - Both expose `complete(system, history, question, jpeg) -> str`.
5. `VisionBrain`:
   - Keep the last `ACCEX_HISTORY_TURNS` text turns, plus action notes from `record_action`.
   - Send only the newest screenshot.
   - API errors → `AccexError("I couldn't reach the AI service. Please try again.")`.
6. `main.py`: latency logging is already in place. Tune `slow_notice_s` and the timeouts.
7. Prompt tuning on the real dashboard and Gmail screens.

**Test alone:**
- `python main.py --mock voice,actions` lets you type questions against the real screen and the real LLM.
- `python -m brain.try_brain "what's on my screen?"` prints the JSON and the latency.
- Unit-test `parse.py` fixtures (clean, fenced, prose around the JSON, invalid, missing fields), history trimming, and that the catalog is in the prompt.

**Done when:**
- The dashboard questions and their follow-ups are answered correctly 5 times out of 5.
- Output is always valid JSON or falls back gracefully.
- Median (p50) LLM latency is 2.5 s or less.
- A network failure is spoken, not a crash.

## Person 3 — actions + demo

**Files:** `actions/registry.py`, `actions/builtin.py`, `actions/executor.py`, `actions/confirm.py`, `actions/try_action.py`, `actions/tests/`, `demo/`, `mocks/actions.py`, `mocks/demo.py`

**Build in this order:**
1. `registry.py`: the `@action(name, description, params, dangerous=False)` decorator fills `REGISTRY`. Adding an action means writing one decorated function.
2. `RegistryExecutor`:
   - Validate the type and params, and scale `x`/`y` with `Screenshot.to_screen`.
   - Catch every exception into `ActionResult(False, <speakable message>)`.
   - `ACCEX_DRY_RUN=1` logs instead of acting.
3. `builtin.py` actions:
   - `open_url`
   - `open_app` (known-apps map, then fallback: Win key → type the name → Enter)
   - `scroll`
   - `press_key`
   - `type_text` (clipboard paste, then restore the clipboard)
   - `click` (`x`, `y`, `target`)
   - `email_reply` (**dangerous**): Gmail `r`, wait, paste the body, `ctrl+enter`, return "Email sent."
4. `KeywordGate` (`confirm.py`):
   - `requires_confirmation` = model flag **or** `spec.dangerous`.
   - `classify`: negation wins; phrases like "do it", "go ahead" and "send it" mean yes.
   - Unit-test a table of replies.
5. `demo/log.py`: a basic JSONL log already works. Extend it if useful.
6. `demo/screens/dashboard.html`: a static sales dashboard with an inline SVG bar chart of 12 months, clear labels, and an obvious highest and lowest month. The numbers must match the demo answers.
7. `demo/checklist.md`:
   - Gmail test account with keyboard shortcuts **on** and the test email staged
   - NVDA settings
   - mic and volume
   - phone hotspot
   - no elevated windows
8. Demo mode (`ACCEX_DEMO=1`): verbose logs and known-good fallbacks (e.g. known paths for `open_app`).

**Test alone:**
- `python main.py --mock voice,brain` runs the scripted brain against real actions.
- `python -m actions.try_action open_url url=https://example.com`
- Unit-test the registry validation and the gate.

**Done when:**
- Every action passes 5 times out of 5 on the demo laptop.
- `email_reply` never runs without "yes".
- An unknown or invalid action gets a spoken explanation.

---

## Timeline (12 h) — merge every branch into `main` at each checkpoint

| Time | Milestone |
|---|---|
| 0:00–0:45 | **CP0:** each person pulls the skeleton, branches, creates a venv, and runs `pytest` and `python main.py --mock all`. |
| 0:45–3:00 | **CP1:** real voice question → real spoken answer about the real screen (P1 + P2). P3 has the registry, the simple actions, the gate and the dashboard. |
| 3:00–6:00 | **CP2:** click, type, `email_reply` and confirmation work on the full demo script, with earcons, "One moment", spoken errors and demo mode. |
| 6:00–8:00 | Polish: latency, robustness in a noisy room, NVDA testing. One stretch goal, and only if CP2 is solid. |
| 8:00–10:00 | **CP3:** feature freeze. Bug fixes only. Rehearse 5 times with timings. |
| 10:00–12:00 | **Code freeze:** backup video, Devpost, rehearsals. |

**Stretch goals, in order:** better TTS voice → speaking through NVDA → streaming responses → UI Automation clicks → transcript overlay for judges → wake word.

## Test plan

- **Per module:** see each person's "Test alone" above. Unit tests run with mocks only.
- **Full loop:** `tests/test_loop_mocks.py` checks:
  - the demo answers
  - `email_reply` only runs after "yes"
  - "no" cancels and "maybe" asks again
  - errors are spoken
  - "One moment" plays when the brain is slow
  - dangerous actions are confirmed even when the model forgets to ask
- **Demo rehearsal:** run the script below 5 times on the demo laptop with `--demo`, and check the latency lines in `logs/`.

## Demo script

1. Turn the monitor off or blindfold the presenter. `demo/screens/dashboard.html` is open full-screen.
2. "What's on my screen?" → a summary of the sales dashboard.
3. "Which month had the highest sales?" → "And the lowest?" (memory)
4. "Read me my latest email." (Gmail test account)
5. "Reply that I'll review it tomorrow." → "Do you want me to send it?" → "Yes." → the email is sent.
6. If anything fails, Accex says so out loud and the presenter moves on. The backup video is recorded at 10:00.

## Risks → fallbacks

| Risk | Fallback |
|---|---|
| Latency over 4 s | Screenshot taken in parallel with recording, 1280 px JPEG, effort `low`, "One moment" after 1.5 s. Model swap in `.env` (team decision). |
| Click accuracy | Prefer keyboard actions (Gmail shortcuts, `press_key`). Rehearse the exact screens. Stretch: UI Automation lookup by name. |
| Hallucinations | The prompt forbids inventing numbers. The dashboard has clear labels. Demo questions are verified 5/5. |
| Loud room | Push-to-talk, headset mic, "Sorry, I didn't catch that." |
| Windows permissions, DPI, UIPI | Mic toggle on the checklist, DPI-aware startup, no elevated windows. Test on the demo laptop by CP1. |
| API or Wi-Fi outage | Phone hotspot, spoken errors, `--mock brain` as a last-resort live fallback, backup video. |
| Talking over NVDA | The PTT key silences NVDA, and Accex speaks before acting. Stretch: speak through NVDA. |
| Gmail UI changes | Shortcuts enabled and the email staged (checklist). `email_reply` rehearsed. |
| Prompt injection | The prompt treats screen text as data, and the gate confirms dangerous actions regardless of the model. |

---

## Senior mode (P2, branch `p2-senior`)

Opt-in with `ACCEX_PROFILE=senior`. With the default profile nothing changes: golden snapshots
in `brain/tests/snapshots/` prove the prompt, payloads and parser are byte-identical.

- **Family profile** `family.json` (copy `family.example.json`; git-ignored): family names,
  relations, aliases, video app, doctor and patient-portal URL. Missing file = works without it.
- **Vague requests**: the model resolves "my grandson" / "that doctor thing" from the profile
  and the screen, acts when one reading is clearly best, and asks at most ONE question with at
  most 2 options (`clarify` field) only when the step has consequences. Enforced in
  `brain/senior.py`: never two questions in a row.
- **Scams** (`risk` field): fake virus/tech-support, gift cards, remote access, urgent bank,
  prizes, relative-in-trouble, crypto. Blocks the action and says "Stop. This looks like a scam".
- **Voice**: shorter, simpler answers; slower ElevenLabs/Windows voice and lower mic threshold
  via `ACCEX_SENIOR_*` env (no voice code changed).
- **Learning**: if the user mentions someone or something Accex can't identify, it asks once
  ("Who is Pablo?") and saves the answer to `family.json` (`remember` field): new people,
  nicknames (aliases) and what vague requests mean (`learned_notes`, max 30). Next session it
  knows. Only learned when the user answers Accex's question or says "remember"; never from
  the screen, `[continue]` steps or scam screens. Edit or delete entries in `family.json` by hand.
- **Family log** `logs/family.jsonl`, one JSON object per line, text only:
  `{"t": unix_time, "kind": "asked|clarified|blocked|learned|done|failed", "text": str, "detail": str}`.
  For the UI/dashboard owner to read; no notifications are sent.
- **Eval**: `python -m brain.eval_senior` (20 vague, 10 clear x 2 profiles, 8 scam + 8 normal
  screens). Live pytest: `ACCEX_LIVE_TESTS=1 pytest tests/test_senior_live.py`.

**For P1 (voice), optional:** to pass family names to speech recognition, add to `OpenAISTT`
in `voice/stt.py`:

```python
    def set_vocabulary(self, words: list[str]) -> None:
        self.hint = VOCABULARY_HINT + " " + ", ".join(words)
```

and use `prompt=getattr(self, "hint", VOCABULARY_HINT)` in `_call`. `main.py` already calls
`set_vocabulary()` in senior mode when it exists.

---

## Minimalist interface (branch `minimalist-interface`)

`python main.py --ui` (or `ACCEX_UI=1`) shows a floating Apple-style glass pill above the
taskbar for people next to the user (family, judges). Without `--ui` nothing changes.

- States: idle, listening (waveform), thinking (shimmer), speaking, acting (Step n with a
  progress bar), waiting for an answer, done, scam blocked (red), error. Expands while
  something happens and collapses afterwards.
- Never takes focus, is click-through, and is excluded from screen capture, so Accex's
  model never sees or clicks it. `ACCEX_UI_CAPTURABLE=1` lets OBS record it for the demo
  video (the model then sees it too).
- Fed by `ui/bridge.py` (TapLog / TapSpeaker wrap the existing EventLog and Speaker); no
  change to `interfaces.py` or the loop. Raw model output never reaches the page.
- `python -m ui.preview` plays every state with fake events (no API) for design reviews.
- Windows only blurs the desktop behind *active* windows, so the glass is a CSS dark
  material rather than a live blur. The frame is rounded by Windows 11 itself (8px,
  anti-aliased, native shadow); the card's CSS radius matches it so there are no black corners.
