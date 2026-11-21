"""Latency and error summary of rehearsal logs (owner: P3).

    python -m demo.latency                  # newest session in logs/
    python -m demo.latency --all            # every session
    python -m demo.latency logs/session-20261121-140000.jsonl

Reads the `latency`, `action_result` and `error` events written by demo/log.py.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from .log import LOG_DIR

FIELDS = ("stt_ms", "capture_ms", "llm_ms", "total_ms")


def read_events(paths: list[Path]) -> list[dict]:
    events = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def summarize(events: list[dict]) -> str:
    lat = [e for e in events if e.get("event") == "latency"]
    lines = [f"turns: {len(lat)}"]
    if lat:
        lines.append(f"{'':12}{'p50':>8}{'p90':>8}{'max':>8}")
        for f in FIELDS:
            vals = [float(e[f]) for e in lat if isinstance(e.get(f), (int, float))]
            if vals:
                lines.append(f"{f:12}{statistics.median(vals):>8.0f}"
                             f"{percentile(vals, 0.9):>8.0f}{max(vals):>8.0f}")
    results = [e for e in events if e.get("event") == "action_result"]
    if results:
        ok = sum(1 for e in results if e.get("ok"))
        lines.append(f"actions: {ok}/{len(results)} ok")
        for e in results:
            if not e.get("ok"):
                lines.append(f"  failed: {e.get('message')}")
    errors = [e for e in events if e.get("event") == "error"]
    lines.append(f"errors: {len(errors)}")
    for e in errors:
        lines.append(f"  {e.get('where')}: {e.get('detail')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Summarize Accex session logs")
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help="every session in logs/")
    args = ap.parse_args(argv)
    paths = args.files or sorted(LOG_DIR.glob("session-*.jsonl"))
    if not args.files and not args.all:
        paths = paths[-1:]
    if not paths:
        print(f"No session logs in {LOG_DIR}", file=sys.stderr)
        return 1
    print(", ".join(p.name for p in paths))
    print(summarize(read_events(paths)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
