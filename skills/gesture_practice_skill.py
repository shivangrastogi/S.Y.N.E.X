"""Gesture practice voice surface.

Skills:
  * ``practice_gesture`` — "practice peace" / "practice gesture peace for 60 seconds"
  * ``practice_status``  — current session state
  * ``practice_stop``    — stop early + return final stats
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


_DURATION_RE = re.compile(r"(?:for\s+|me\s+|mein\s+)?(\d+)\s*(s|sec|seconds?|min|minutes?)?",
                          re.IGNORECASE)
_VERB_STRIP_RE = re.compile(
    r"^(?:please\s+)?"
    r"(?:practice\s+gesture|practice|gesture\s+practice\s+karo|"
    r"practice\s+karo|gesture\s+practice)\s+",
    re.IGNORECASE,
)


def _parse(text: str) -> tuple[str, int]:
    body = _VERB_STRIP_RE.sub("", text.strip())
    duration = 30
    # Pull a duration if present, then strip it from the body.
    m = _DURATION_RE.search(body)
    if m:
        n = int(m.group(1))
        unit = (m.group(2) or "seconds").lower()
        duration = max(5, min(600, n * (60 if unit.startswith(("m", "min")) else 1)))
        body = body[:m.start()].strip()
    # Whatever's left is the target gesture name.
    target = body.strip(" .,?\"'")
    return target, duration


@skill(
    name="practice_gesture",
    description="Start a focused practice session for one gesture — counts "
                "hits over a window (default 30 s).",
    patterns=[
        "practice gesture", "practice", "gesture practice karo",
        "practice peace", "practice double pinch",
        "gesture practice", "practice karo", "practice the gesture",
    ],
    required_entities=[],
)
def practice_gesture(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    target, duration = _parse(text)
    if not target:
        return ("Kaunsa gesture practice karna hai? "
                "e.g. 'practice peace for 30 seconds'.")
    try:
        from core.gesture_practice import start_practice
    except Exception as e:
        return f"gesture_practice load fail: {e}"
    sess = start_practice(target, duration)
    if sess.get("error"):
        return sess["error"]
    return (f"Practice session ON — target '{target}', {duration}s window. "
            f"Say 'practice status' anytime, 'practice stop' to end early.")


@skill(
    name="practice_status",
    description="Report current gesture-practice session stats.",
    patterns=[
        "practice status", "gesture practice status",
        "kya practice chal raha hai", "how many hits",
        "practice ka result",
    ],
    required_entities=[],
)
def practice_status(_slots: dict) -> str:
    try:
        from core.gesture_practice import status as _status
    except Exception as e:
        return f"gesture_practice load fail: {e}"
    sess = _status()
    if sess is None:
        return "Koi practice session chal raha nahi."
    target = sess.get("target", "?")
    hits = sess.get("hits", 0)
    misses = sess.get("misses", 0)
    acc = sess.get("accuracy", 0.0)
    rem = sess.get("remaining_s", 0)
    state = "RUNNING" if sess.get("running") else "DONE"
    return (f"Practice ({target}) [{state}]: "
            f"hits={hits} misses={misses} accuracy={int(acc * 100)}% "
            f"remaining={rem}s")


@skill(
    name="practice_stop",
    description="Stop the current gesture-practice session and return stats.",
    patterns=[
        "practice stop", "stop practice", "practice band karo",
        "gesture practice stop", "end practice",
        "stop gesture practice",
    ],
    required_entities=[],
)
def practice_stop(_slots: dict) -> str:
    try:
        from core.gesture_practice import stop_practice
    except Exception as e:
        return f"gesture_practice load fail: {e}"
    sess = stop_practice()
    if sess is None:
        return "Koi practice session chal raha nahi tha."
    hits = sess.get("hits", 0)
    misses = sess.get("misses", 0)
    acc = sess.get("accuracy", 0.0)
    return (f"Practice stopped — hits={hits}, misses={misses}, "
            f"accuracy={int(acc * 100)}%.")
