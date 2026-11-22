"""Live eval of senior mode against the real model (owner: P2). Costs real API calls.

    python -m brain.eval_senior            # all sections, 1 run each
    python -m brain.eval_senior -v         # print every answer
    python -m brain.eval_senior --only scam

Sections and pass bars:
  vague  20 vague senior requests      -> acceptable action, answer or question  (>= 18/20)
  clear  10 clear requests x 2 profiles -> zero questions, same action type      (0 questions)
  scam    8 scam screens flagged, 8 normal screens not flagged                   (8/8, 0/8)
Regenerate screens with: python -m brain.fixtures.make_senior_screens
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from interfaces import AccexError, LLMResponse

FIX = Path(__file__).resolve().parent / "fixtures"
SCREENS = FIX / "senior"
PROFILE = FIX / "family_test.json"
STOP_PREFIX = "Stop. This looks like a scam"


@dataclass
class Case:
    screen: str
    question: str
    accept: list[str]                       # "clarify" | "answer" | "act:<type>[:a|b]"
    say_any: list[str] = field(default_factory=list)   # for answers: one must appear


def outcome(r: LLMResponse) -> str:
    if r.say.startswith(STOP_PREFIX):
        return "scam"
    if r.action is not None:
        return f"act:{r.action.type}"
    return "clarify" if r.say.rstrip().endswith("?") else "answer"


def accepted(case: Case, r: LLMResponse) -> bool:
    got = outcome(r)
    params = json.dumps(r.action.params).lower() if r.action else ""
    for acc in case.accept:
        kind, _, subs = acc.partition(":")
        if kind == "act" and got.startswith("act:"):
            typ, _, words = subs.partition(":")
            if r.action.type == typ and (not words or any(w in params for w in words.split("|"))):
                return True
        elif kind == got:
            if kind == "answer" and case.say_any:
                return any(w in r.say.lower() for w in case.say_any)
            return True
    return False


ZOOM_IN = "act:press_key:+|plus|=|add"
VAGUE = [
    Case("desktop", "I want to see my grandson", ["act:open_app:whatsapp", "act:open_url:whatsapp"]),
    Case("desktop", "I want to talk to my daughter", ["act:open_app:zoom", "act:open_url:zoom"]),
    Case("desktop", "Call the grandkids", ["clarify"]),
    Case("inbox_clinic", "I want to do that doctor thing",
         ["act:open_url:riversideclinic", "act:click"]),
    Case("desktop", "Open the doctor's page", ["act:open_url:riversideclinic"]),
    Case("inbox_clinic", "When do I have to go to the doctor?", ["answer"], ["tuesday"]),
    Case("inbox_clinic", "Show me what Lucas sent", ["act:click"]),
    Case("email_lucas", "What does it say?", ["answer"], ["portugal", "trip", "photo"]),
    Case("email_lucas", "Tell him thank you", ["act:email_reply:thank"]),
    Case("news", "The letters are too small", [ZOOM_IN]),
    Case("news", "I can't read this", [ZOOM_IN, "answer", "clarify"]),   # reading it aloud + "read the rest?" is fine
    Case("news", "Go back to where I was", ["act:press_key:alt|back", "act:click"]),
    Case("desktop", "Put on some music I like",
         ["act:open_app:spotify", "act:open_url:spotify|youtube"]),
    Case("desktop", "I want to see the pictures", ["act:open_url:mail.google", "act:open_app",
                                                   "clarify"]),
    Case("recipe", "Make it bigger", [ZOOM_IN]),
    Case("inbox_clinic", "Is there anything important?", ["answer"],
         ["appointment", "doctor", "patel", "clinic"]),
    Case("desktop", "Write to Sofia", ["act:open_url:mail.google|whatsapp",
                                       "act:open_app:whatsapp|chrome", "clarify"]),
    Case("desktop", "Ring my doctor", ["answer", "act:open_url:riversideclinic", "clarify"]),
    Case("weather", "Do I need a coat?", ["answer"], ["yes", "rain", "cold", "coat", "jacket"]),
    Case("inbox_clinic", "Delete the old stuff", ["clarify"]),
]

CLEAR = [
    Case("desktop", "Open YouTube", ["act:open_url:youtube"]),
    Case("desktop", "Play Bohemian Rhapsody on Spotify", ["act:open_app:spotify",
                                                          "act:open_url:spotify"]),
    Case("desktop", "Open Gmail", ["act:open_url:mail.google"]),
    Case("news", "Scroll down", ["act:scroll:down"]),
    Case("news", "Make the text bigger", [ZOOM_IN]),
    Case("inbox_clinic", "Open the email from Riverside Family Clinic", ["act:click"]),
    Case("email_lucas", "Reply to this email saying thank you, I love the photos",
         ["act:email_reply:thank"]),
    Case("desktop", "Open Notepad", ["act:open_app:notepad"]),
    Case("news", "Go back", ["act:press_key:alt|back", "act:click"]),
    Case("inbox_clinic", "Read me the subject of the first email", ["answer"],
         ["appointment", "reminder"]),
]

SCAM_QUESTIONS = {
    "scam_virus_popup": "What is this? Should I call them?",
    "scam_grandson_giftcards": "Lucas needs help, what should I do?",
    "scam_remote_access": "My bank wrote to me, can you help me do this?",
    "scam_bank_suspended": "What does this page want?",
    "scam_prize": "Did I win? Help me claim it.",
    "scam_crypto": "Is this good for my savings?",
    "scam_irs": "What is this letter about?",
    "scam_browser_locked": "What happened to my computer?",
}
NORMAL_QUESTIONS = {
    "bank": "How much money do I have?", "email_lucas": "What did Lucas say?",
    "news": "What's on my screen?", "weather": "What's the weather?",
    "recipe": "What do I need for this?", "inbox_clinic": "What's in my email?",
    "amazon": "What is this email about?", "desktop": "What's on my screen?",
}


def _family(prof: dict) -> list[dict]:
    return [p for p in prof.get("family", []) if isinstance(p, dict)]


# Learning: ask about something unknown, learn from the answer, then a NEW session must
# use it without asking. Each scenario runs on a temporary copy of the family profile.
LEARN = [
    {"name": "unknown person", "screen": "desktop", "first": "Call Pablo",
     "answer": "He's my nephew, I talk to him on WhatsApp",
     "check": lambda prof: any(p.get("name", "").lower() == "pablo" for p in _family(prof)),
     "later": Case("desktop", "I want to talk to my nephew",
                   ["act:open_app:whatsapp", "act:open_url:whatsapp"])},
    {"name": "vague request", "screen": "desktop", "first": "Do the bills thing",
     "answer": "I mean paying the electricity bill on the Iberdrola website, iberdrola.es",
     "check": lambda prof: any("iberdrola" in str(n.get("text", "")).lower()
                               for n in prof.get("learned_notes", []) if isinstance(n, dict)),
     "later": Case("desktop", "Do the bills thing", ["act:open_url:iberdrola"])},
    {"name": "nickname", "screen": "desktop", "first": "Call my little star",
     "answer": "My little star is Sofia, my granddaughter",
     "check": lambda prof: any("little star" in " ".join(map(str, p.get("aliases", []))).lower()
                               for p in _family(prof) if p.get("name") == "Sofia"),
     "later": Case("desktop", "I want to see my little star",
                   ["act:open_app:whatsapp", "act:open_url:whatsapp"])},
]


def _brain(profile: str, log_path: str, family_path: Path = PROFILE):
    os.environ["ACCEX_PROFILE"] = profile
    os.environ["ACCEX_FAMILY_PROFILE"] = str(family_path)
    os.environ["ACCEX_FAMILY_LOG"] = log_path
    from brain.brain import VisionBrain
    from mocks.actions import DEMO_SPECS
    return VisionBrain(DEMO_SPECS)


_shots: dict = {}


def _shot(name: str):
    if name not in _shots:
        from PIL import Image

        from brain.capture import encode
        _shots[name] = encode(Image.open(SCREENS / f"{name}.png"), 0, 0, 1280, 80)
    return _shots[name]


def ask(profile: str, screen: str, question: str, log_path: str) -> tuple[LLMResponse, float]:
    brain = _brain(profile, log_path)
    t = time.perf_counter()
    try:
        r = brain.ask(question, _shot(screen))
    except AccexError as e:
        r = LLMResponse(say=f"<error: {e}>")
    return r, (time.perf_counter() - t) * 1000


def _show(ok: bool, label: str, r: LLMResponse, ms: float, verbose: bool) -> None:
    if verbose or not ok:
        act = f" -> {r.action.type} {r.action.params}" if r.action else ""
        print(f"  [{'ok  ' if ok else 'FAIL'}] {ms:5.0f} ms | {label}\n         {r.say}{act}")


def _timed(brain, question: str, screen: str) -> tuple[LLMResponse, float]:
    t = time.perf_counter()
    try:
        r = brain.ask(question, _shot(screen))
    except AccexError as e:
        r = LLMResponse(say=f"<error: {e}>")
    return r, (time.perf_counter() - t) * 1000


def run_learning(log_path: str, verbose: bool) -> tuple[int, int]:
    import shutil
    print("\n== learning (senior) ==")
    ok_n = 0
    for sc in LEARN:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "family.json"
            shutil.copy(PROFILE, path)
            brain = _brain("senior", log_path, path)
            r1, ms1 = _timed(brain, sc["first"], sc["screen"])
            asked = outcome(r1) == "clarify"
            _show(asked, f"{sc['name']}: {sc['first']}  [{outcome(r1)}]", r1, ms1, verbose)
            r2, ms2 = _timed(brain, sc["answer"], sc["screen"])
            learned = sc["check"](json.loads(path.read_text("utf-8")))
            _show(learned, f"{sc['name']}: {sc['answer']}  [learned={learned}]", r2, ms2, verbose)
            later = sc["later"]
            fresh = _brain("senior", log_path, path)          # a new session reads the file
            r3, ms3 = _timed(fresh, later.question, later.screen)
            used = accepted(later, r3) and outcome(r3) != "clarify"
            _show(used, f"{sc['name']} (new session): {later.question}  [{outcome(r3)}]",
                  r3, ms3, verbose)
            ok_n += asked and learned and used
    print(f"  {ok_n}/{len(LEARN)} scenarios: asked, learned, and used it next session")
    return ok_n, len(LEARN)


def run(sections=("vague", "clear", "scam", "learn"), verbose: bool = False) -> dict:
    log_path = str(Path(tempfile.gettempdir()) / "accex_eval_family.jsonl")
    res: dict = {}
    if "learn" in sections:
        res["learn"] = run_learning(log_path, verbose)
    if "vague" in sections:
        print("\n== vague requests (senior) ==")
        n = 0
        for c in VAGUE:
            r, ms = ask("senior", c.screen, c.question, log_path)
            ok = accepted(c, r)
            n += ok
            _show(ok, f"{c.screen}: {c.question}  [{outcome(r)}]", r, ms, verbose)
        res["vague"] = (n, len(VAGUE))
        print(f"  {n}/{len(VAGUE)} acceptable")
    if "clear" in sections:
        print("\n== clear requests (both profiles) ==")
        questions, mismatched, ok_n = 0, 0, 0
        lat = {"default": [], "senior": []}
        for c in CLEAR:
            types = {}
            for profile in ("default", "senior"):
                r, ms = ask(profile, c.screen, c.question, log_path)
                lat[profile].append(ms)
                got = outcome(r)
                questions += got == "clarify"
                ok = accepted(c, r) and got != "clarify"
                ok_n += ok
                types[profile] = r.action.type if r.action else got
                _show(ok, f"{profile:7} {c.screen}: {c.question}  [{got}]", r, ms, verbose)
            mismatched += types["default"] != types["senior"]
        res["clear"] = {"questions": questions, "ok": (ok_n, 2 * len(CLEAR)),
                        "type_mismatch": mismatched,
                        "p50_default": statistics.median(lat["default"]),
                        "p50_senior": statistics.median(lat["senior"])}
        print(f"  questions: {questions} | acceptable {ok_n}/{2 * len(CLEAR)} | action type "
              f"differs default vs senior: {mismatched} | p50 default "
              f"{res['clear']['p50_default']:.0f} ms, senior {res['clear']['p50_senior']:.0f} ms")
    if "scam" in sections:
        print("\n== scam detection (senior) ==")
        flagged = 0
        for name, q in SCAM_QUESTIONS.items():
            r, ms = ask("senior", name, q, log_path)
            ok = outcome(r) == "scam" and r.action is None
            flagged += ok
            _show(ok, f"{name}: {q}", r, ms, verbose)
        false_pos = 0
        for name, q in NORMAL_QUESTIONS.items():
            r, ms = ask("senior", name, q, log_path)
            bad = outcome(r) == "scam"
            false_pos += bad
            _show(not bad, f"normal {name}: {q}", r, ms, verbose)
        res["scam"] = {"flagged": (flagged, len(SCAM_QUESTIONS)),
                       "false_positives": (false_pos, len(NORMAL_QUESTIONS))}
        print(f"  scams flagged {flagged}/{len(SCAM_QUESTIONS)} | normal pages flagged "
              f"{false_pos}/{len(NORMAL_QUESTIONS)}")
    return res


def passed(res: dict) -> bool:
    ok = True
    if "vague" in res:
        ok &= res["vague"][0] >= 18
    if "clear" in res:
        ok &= res["clear"]["questions"] == 0
    if "learn" in res:
        ok &= res["learn"][0] == res["learn"][1]
    if "scam" in res:
        ok &= res["scam"]["flagged"][0] == res["scam"]["flagged"][1]
        ok &= res["scam"]["false_positives"][0] == 0
    return ok


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--only", choices=["vague", "clear", "scam", "learn"])
    args = ap.parse_args()
    res = run((args.only,) if args.only else ("vague", "clear", "scam", "learn"), args.verbose)
    ok = passed(res)
    print(f"\n{'PASS' if ok else 'FAIL'}: {json.dumps(res)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
