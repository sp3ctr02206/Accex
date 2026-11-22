# /brag plan: Accex

## Rubric
- **What is it?** An AI digital navigator: a voice assistant for people who never learned to use a computer. You hold a key and ask out loud, in your own words. It looks at your screen, does the task step by step and tells you what it's doing.
- **Who is it for?** People who are digitally illiterate: older adults, workers who never needed a computer, anyone locked out of online services because nobody taught them. They need no computer words and no mouse skills.
- **What sets it apart?**
  - It understands vague requests using a profile of the user's family.
  - It acts until the task is done and narrates every step, so it's never a black box.
  - It asks for a spoken "yes" before sending, deleting or buying anything, and that rule is enforced in code.
  - It checks every screen for scams and stops them before anything is clicked.
- **Most impressive claim:** "Play Bohemian Rhapsody on Spotify" becomes four real actions, narrated, ending with the song playing, with nobody touching the mouse. Then comes a fake "your grandson needs gift cards" email, and Accex refuses: "Stop. This looks like a scam."
- **Visual hook:** a cluttered screen with icons, pop-ups and a cursor that doesn't know where to go (what the user feels). Then the glass pill lights up as it listens.
- **Real UI shown:** the actual pill from `ui/web/`: its `style.css` is loaded as-is, the markup is copied from `index.html`, and the state names, step labels and colors come from `app.js`. The event script is the one in `ui/preview.py`.
- **Tone:** polished, with a warm edge. Clean Apple-style glass, calm confidence, no forced jokes.
- **Share caption:** "Accex: ask out loud, in your own words, and your computer does the rest, and stops scams along the way. An AI digital navigator for everyone who was never taught how to use a computer. Built at Cutie Hack 2026."

## Visual identity (from ui/web/style.css)
- **Glass:** `rgb(30,31,38)` with a white specular rim.
- **State colors:**
  - listening: `#64d2ff #0a84ff #5e5ce6`
  - thinking: `#bf5af2 #5e5ce6 #ff375f`
  - acting: `#0a84ff #64d2ff #30d158`
  - done: `#30d158`
  - blocked: `#ff453a`
  - senior badge: `#ffd60a`
- **Font:** Segoe UI Variable Display (the pill's own font stack).

## Storyboard: 20.0 s, 1920×1080, 30 fps, 120 BPM (one beat = 0.5 s), every cut on a beat

| # | Time | Scene | On screen | Sound |
|---|---|---|---|---|
| 1 Hook | 0.0–3.0 | Cluttered desktop | Messy icons ("New folder (3)", "Setup (2).exe", "taxes_FINAL_v2"…). Three pop-ups pile up (updates, notifications, storage) while a lost cursor wanders. The screen dims, then "Lost on your computer?" builds and holds from 0.9 to 2.0. "Just ask." holds from 2.1 to 3.0. | Low pad. A soft notification ding in key for each pop-up. |
| 2 Reveal | 3.0–7.0 | The pill blooms in the centre at 2.2× | Kicker "Hold a key · ask in your own words". The idle pill switches to **Listening**. The quote “Play Bohemian Rhapsody on Spotify” types in and holds. At 5.5 the pill expands with a YOU line and shows **Thinking**. | The beat drops at 3.0. Listening earcon. |
| 3 Acts | 7.0–13.0 | Desktop with a generic music app and the pill docked bottom-centre (1.5×) | Headline "It does every click. And tells you each step." Steps land on beats: 7.5 Opening Spotify, 8.5 Clicking the search box, 9.0 Typing, 10.0 Pressing enter. At 10.5 the pill shows **Done**, the progress bar reaches 100% and the reply reads "Bohemian Rhapsody by Queen is now playing on Spotify." | Hats and arp. Clicks, key ticks, a done chime. |
| 4 Scams | 13.0–17.0 | Generic mail window, fake-grandson email (from fixture `scam_grandson_giftcards.png`) | YOU line “Lucas needs help, what should I do?”. At 14.0 the pill shows **Scam blocked**: "Stop. This looks like a scam…". The gift-card line gets a red outline. Headline "And it stops scams before you click." | Drums thin out. A low D-minor stab at 14.0. |
| 5 Outro | 17.0–20.0 | Big orb | "Accex", then "Ask in your own words.", then "An AI digital navigator · Built at Cutie Hack 2026". | Resolve to F, bells, a long tail. |

Durations: 3 + 4 + 6 + 4 + 3 = **20 s** (600 frames).

## Notes
- **Brands:** the music app, mail window and desktop are generic stand-ins. There are no Spotify, Gmail or Windows logos; Spotify is only named as the user's spoken words.
- **Names:** "Lucas" is the fictional grandson from the test fixtures. There is no real data, keys or email.
- **Repo:** it is private, so the outro names the hackathon instead of a URL.
- **Music:** synthesized in numpy. F major (Dm9 · B♭maj7 · Fmaj7 · Am7 · Dm7 …), going darker under the scam scene and resolving to Fmaj9 in the outro. Effects use the same key and grid.
