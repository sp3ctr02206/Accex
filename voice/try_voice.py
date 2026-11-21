"""Manual voice check (owner: P1).

    python -m voice.try_voice

Hold the push-to-talk key, speak, release: prints the transcript and STT latency, then
speaks it back. A quick tap interrupts the playback. Ctrl+C quits.
"""
from __future__ import annotations

import time

from interfaces import AccexError


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    import voice

    speaker = voice.create_speaker()
    stt = voice.create_stt()
    listener = voice.create_listener()

    def on_start() -> None:
        speaker.stop()
        speaker.cue("listening")

    speaker.say("Voice test. Hold the key and talk.")
    print(f"Hold {listener.hotkey_name} and talk. Ctrl+C to quit.")
    n = 0
    try:
        while True:
            try:
                clip = listener.wait_for_utterance(on_start)
                speaker.cue("thinking")
                t0 = time.perf_counter()
                text = stt.transcribe(clip)
                ms = round((time.perf_counter() - t0) * 1000)
                n += 1
                print(f"#{n} [{clip.duration_s:.1f}s audio, STT {ms} ms] {text!r}")
                t1 = time.perf_counter()
                speaker.say(text or "Sorry, I didn't catch that.")
                print(f"    say() returned in {round((time.perf_counter() - t1) * 1000)} ms")
            except AccexError as e:
                print(f"[ERROR] {e.spoken} ({e})")
                speaker.cue("error")
                speaker.say(e.spoken)
    except KeyboardInterrupt:
        pass
    finally:
        speaker.stop()
        listener.close()


if __name__ == "__main__":
    main()
