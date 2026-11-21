# Demo checklist (owner: P3)

Run through this on the **demo laptop** before every rehearsal and before going on stage.

## 1. Laptop & Windows

- [ ] Plugged in, power mode **Best performance**, sleep and screen saver **off**.
- [ ] **Focus assist / Do not disturb on** (no notifications over the demo screen).
- [ ] Windows Update paused; no pending restart.
- [ ] **No elevated (admin) windows open.** Accex can't type or click into them (UIPI), and
      the push-to-talk hook doesn't fire there. Don't run the terminal as administrator.
- [ ] Display scaling noted (Settings → Display). `main.py` is DPI-aware, but rehearse
      at the same scaling you'll present with. Single monitor, or the demo on the **primary** one.
- [ ] Mouse parked mid-screen. Moving it to a corner triggers the pyautogui fail-safe and
      stops the action ("I stopped because the mouse was moved to a corner").

## 2. Audio

- [ ] Headset mic plugged in and chosen: set `ACCEX_MIC_DEVICE` in `.env` if it isn't the default.
- [ ] **Settings → Privacy & security → Microphone → Let desktop apps access your microphone: On.**
- [ ] Output volume loud enough for the room (test with the venue speakers if there are any).
      Earcons and speech both audible.
- [ ] Room test: `python -m voice.try_voice`, 3 questions transcribed correctly.

## 3. NVDA

- [ ] NVDA running (if part of the demo), version noted.
- [ ] Push-to-talk is **Right Ctrl**; this also silences NVDA. NVDA modifier is **Insert** or
      **CapsLock**, never the Accex hotkey.
- [ ] NVDA speech rate and volume set so it doesn't talk over Accex (Accex speaks before acting).
- [ ] Optional: NVDA → Settings → Speech → "Speak typed characters" **off** (pasting is silent,
      but typed fallbacks in the Start menu would be read out).

## 4. Network & keys

- [ ] Venue Wi-Fi works **and** the phone hotspot is set up and tested as a backup.
- [ ] `.env` has `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`; quick check:
      `python -m brain.try_brain "what's on my screen?"`.
- [ ] `--mock brain` fallback known by heart: `python main.py --mock brain`.

## 5. Browser & Gmail (test account only)

- [ ] Default browser opens with `python -m actions.try_action open_url url=https://example.com`.
- [ ] Logged in to the **Gmail test account** (never a personal account).
- [ ] Gmail → Settings → See all settings → General → **Keyboard shortcuts on** → Save.
      (`email_reply` uses `r` to reply and `Ctrl+Enter` to send.)
- [ ] **Test email staged:** from Maria Lopez, subject **"Q3 report"**, asking to review the attached
      report before Friday. It is the newest email in the inbox, unread.
- [ ] Before step 4 of the script the email is **open** (not just the inbox list), and the
      browser window has focus. Nothing typed into the search box.
- [ ] Sent folder cleaned after each rehearsal; the test email re-staged (marked unread, on top).
- [ ] Browser zoom 100%, bookmarks bar hidden, no other tabs with notifications.

## 6. Demo screen

- [ ] `demo/screens/dashboard.html` open in the browser, **full screen (F11)**.
- [ ] Expected answers (the numbers on the dashboard):
  - What's on my screen → sales dashboard for 2026, monthly bar chart, total **$1.24 million**.
  - Highest month → **March, $142,000**.
  - Lowest month → **August, $61,000**.
- [ ] Switching dashboard → Gmail rehearsed (Alt+Tab or a second tab, one keystroke).

## 7. Accex

- [ ] On the demo branch, up to date: `git pull`, `pytest` green.
- [ ] Dry run of the whole script first: `python main.py --demo --dry-run`.
- [ ] Real run: `python main.py --demo` (`ACCEX_DEMO=1`: verbose logs + known app paths).
- [ ] After each rehearsal: `python -m demo.latency` and check p50 total ≤ 4 s.
- [ ] Each action 5/5 with `python -m actions.try_action ...` (`--list` shows them all).

## 8. Script (from PLAN.md)

1. Monitor off / presenter blindfolded. Dashboard full screen.
2. "What's on my screen?"
3. "Which month had the highest sales?" → "And the lowest?"
4. "Read me my latest email."
5. "Reply that I'll review it tomorrow." → "Do you want me to send it?" → "Yes." → "Email sent."
6. Anything fails → Accex says so out loud, presenter moves on. Backup video ready.

## 9. If something breaks on stage

| Symptom | Do this |
|---|---|
| No reaction to Right Ctrl | A window is elevated or focus is weird: click the browser once, try again. |
| "I couldn't reach the AI service" | Switch to the hotspot; worst case restart with `--mock brain`. |
| Reply didn't send | Gmail lost focus or shortcuts off: say it, move on, show the backup video. |
| Accex talks over NVDA | Tap Right Ctrl to silence both, ask again. |
