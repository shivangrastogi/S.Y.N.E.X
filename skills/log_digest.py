"""Today's AERIS log digest — punch-list summary of data/logs/aeris.log.

Parses lines that look like:
    2026-05-24T19:19:35 INFO  module.name :: message body

Buckets entries into:
  * boots          — `boot_start` events
  * crashes        — `crash_recovered` or "Traceback" / `ERROR` lines
  * gestures       — `gestures]` substring (gesture engine logs)
  * brain          — `core.brain`, `intent_classifier`
  * vision         — `vision`, `face`, `auto_label`
  * other          — everything else

Skill: ``log_digest_today`` / "summarize logs" / "aaj ke logs"
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path

from core.skill_registry import skill

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parents[1]
_LOG_PATH = _HERE / "data" / "logs" / "aeris.log"


_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+"
    r"(?P<lvl>[A-Z]+)\s+"
    r"(?P<mod>[\w.]+)\s+::\s+"
    r"(?P<msg>.*)$"
)


def _classify(line: str) -> str:
    if "boot_start" in line:
        return "boots"
    if "crash_recovered" in line or "Traceback" in line:
        return "crashes"
    if "ERROR" in line and "ERROR_HANDLED" not in line:
        return "errors"
    if "gestures]" in line or "gesture_trace" in line:
        return "gestures"
    if "vision]" in line or "face_recognition" in line or "auto_label" in line:
        return "vision"
    if "core.brain" in line or "intent_classifier" in line or "intent_model" in line:
        return "brain"
    if "shutdown" in line:
        return "shutdowns"
    return "other"


@skill(
    name="log_digest_today",
    description="Summarize today's data/logs/aeris.log entries by category.",
    patterns=[
        "summarize logs", "log digest", "logs digest",
        "aaj ke logs batao", "today's logs", "log summary",
        "what happened today", "system log digest",
        "today log summary", "logs ka summary",
    ],
    required_entities=[],
)
def log_digest_today(_slots: dict) -> str:
    if not _LOG_PATH.exists():
        return f"Log file nahi mila: {_LOG_PATH}"
    today = date.today().isoformat()
    try:
        with open(_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Log read fail: {e}"
    todays = [ln for ln in lines if ln.startswith(today)]
    if not todays:
        return f"Aaj ({today}) ke koi logs nahi hain."
    buckets: Counter = Counter()
    sample: dict[str, str] = {}
    for ln in todays:
        cat = _classify(ln)
        buckets[cat] += 1
        if cat not in sample:
            m = _LINE_RE.match(ln.rstrip("\n"))
            if m:
                sample[cat] = f"{m.group('ts')} {m.group('mod')} :: {m.group('msg')[:80]}"
            else:
                sample[cat] = ln.rstrip("\n")[:120]

    order = ["boots", "shutdowns", "crashes", "errors",
             "gestures", "vision", "brain", "other"]
    lines_out = [f"Today's log ({today}) — {len(todays)} entries:"]
    for cat in order:
        if cat not in buckets:
            continue
        lines_out.append(f"  • {cat:10s} {buckets[cat]:4d}   first: {sample[cat]}")
    return "\n".join(lines_out)
