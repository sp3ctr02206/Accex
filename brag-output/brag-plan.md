# /brag plan: Accex

## Rubric
- **What is it?** A voice assistant for blind and low-vision people. You hold a key and ask out loud; it looks at your screen, answers, and does the clicking for you.
- **Who is it for?** People who can't see the screen (and, in senior mode, grandparents). They can use their computer without a mouse or eyesight.
- **What sets it apart?** It *acts* step by step until the task is done instead of just reading things out. It asks for a spoken "yes" before sending, deleting or buying anything. Senior mode stops scams before anything is clicked.
- **Most impressive claim:** "Play Bohemian Rhapsody on Spotify" becomes four real actions, narrated, ending with the song playing, with nobody touching the mouse.
- **Visual hook:** a black screen (what the user sees), then the glass pill lighting up as it listens.
- **Real UI shown:** the actual pill from `ui/web/`: its `style.css` is loaded as-is, the markup is copied from `index.html`, and the state names, step labels and colors come from `app.js`. The event script is the one in `ui/preview.py`.
- **Tone:** `polished` with a warm edge. Clean Apple-style glass, calm confidence, no jokes forced.
- **Share caption:** "Accex: hold a key, ask out loud, and your computer does the rest. A voice assistant for blind and low-vision users. Built at Cutie Hack 2026."

## Visual identity (from ui/web/style.css)
- **Glass:** `rgb(30,31,38)` with a white specular rim. Text is `rgba(255,255,255,.96)`, secondary text `rgba(235,235,245,.62)`.
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
| 1 Hook | 0.0–3.0 | Black screen | "Can't see your screen?" builds word by word and holds from 0.6 to 2.0. Then "Just ask." holds from 2.1 to 3.0. | Low pad, sub swell. Nothing else. |
| 2 Reveal | 3.0–7.0 | The pill blooms in the centre at 2.2× | Kicker "ACCEX". The idle pill switches to **Listening** (wave bars). The quote “Play Bohemian Rhapsody on Spotify” types in from 3.6 to 4.8 and holds. At 5.5 the pill expands with a YOU line. At 6.0 it shows **Thinking**, "Looking at your screen…". | The beat drops at 3.0. Listening earcon at 3.5. |
| 3 Acts | 7.0–13.0 | Windows-style desktop with a generic music app and the pill docked bottom-centre (1.5×) | Headline "It sees your screen. It does the clicks." Steps land on beats: 7.5 Opening Spotify (the app window springs in), 8.5 Clicking the search box (cursor glides and clicks), 9.5 Typing “Bohemian Rhapsody Queen”, 10.5 Pressing enter (the result appears and the play bar starts). At 11.0 the pill shows **Done**, the progress bar reaches 100% and the reply reads "Bohemian Rhapsody by Queen is now playing on Spotify." | Hats come in. Soft clicks and key ticks. A done chime in key at 11.0. |
| 4 Scams | 13.0–17.0 | Mail window (generic, rebuilt from fixture `scam_grandson_giftcards.png`) with a Senior badge on the pill | YOU line: “Lucas needs help, what should I do?”. At 14.0 the pill turns red, **Scam blocked**: "Nothing was clicked or paid". The gift-card line on the email gets a red outline. Headline "Senior mode stops scams." | Drums thin out. A low minor stab at 14.0. |
| 5 Outro | 17.0–20.0 | Dark, the big orb centred | "Accex" wordmark, then "Your computer, by voice." from 17.5, then "For blind & low-vision users · Built at Cutie Hack 2026" from 18.0. All hold to the end. | Resolving chord, chime, a long tail. |

Durations: 3 + 4 + 6 + 4 + 3 = **20 s** (600 frames).

## Notes
- **Brands:** the music app and mail window are generic stand-ins. There are no Spotify or Gmail logos and no browser chrome; Spotify is only named as the user's spoken words.
- **Names:** "Lucas" is the fictional grandson from the test fixtures. There is no real data, keys or email.
- **Repo:** it is private, so the outro names the hackathon instead of a URL.
- **Music:** synthesized in numpy. F major (Fmaj7 · Am7 · Dm7 · B♭maj7, one chord per bar), going darker (Dm · B♭) under the scam scene and resolving to F in the outro. Effects use the same key and grid.
