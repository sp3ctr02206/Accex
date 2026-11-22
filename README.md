# Accex

A voice-first AI assistant for blind and low-vision users. Hold a key and ask a question. Accex looks at your screen, answers out loud, and can act for you: open, scroll, type, click, or reply to an email. Before anything that sends, deletes, buys or submits, it asks you for a spoken "yes".

Built for Cutie Hack 2026 (Social Impact + AI tracks).

## Setup (Windows 11, Python 3.12 or 3.13)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then add your API keys
```

Turn on **Settings → Privacy & security → Microphone → Let desktop apps access your microphone**.

## Run

```powershell
python main.py --mock all              # no keys needed: type questions, read the spoken answers
python main.py --mock brain,actions    # real voice, fake brain and actions
python main.py                         # everything real
python main.py --demo --dry-run        # print every event; log actions instead of running them
python main.py --ui                    # with the floating glass pill
python -m ui.preview                   # design preview of the pill (no API)
pytest                                 # tests
```

Hold **Right Ctrl** to talk and release it to send. A quick tap stops Accex speaking. Pressing Ctrl also silences NVDA.

## Layout

| Path | Owner | What |
|---|---|---|
| `interfaces.py` | all (frozen) | Shared data types and protocols |
| `main.py` | P2 | Orchestration loop, real/mock wiring |
| `voice/` | P1 | Push-to-talk, recording, STT, TTS, earcons |
| `brain/` | P2 | Screen capture, vision LLM, prompt, memory |
| `actions/` | P3 | Action registry, executor, confirmation |
| `demo/` | P3 | Event log, demo screens, demo checklist |
| `ui/` | minimalist-interface | Floating glass pill (pywebview), opt-in with `--ui` |
| `mocks/` | each owner | Fakes for every package |

See [PLAN.md](PLAN.md) for the team plan.

## Privacy

Screenshots and audio stay in memory and are never written to disk. Text on the screen is treated as data, not as instructions. API keys live in `.env`, which is never committed.
