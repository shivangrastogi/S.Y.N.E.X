"""Narrative "what did you change?" over the structured event stream.

Where ``activity_digest`` answers *"how many commands ran"* with skill counts,
this answers *"what happened"* as a short multi-category narrative: skills run,
scheduled routines fired, presence moments, and any other event kind AERIS
logs. It reads the same JSON-line event stream (via
``activity_digest.read_events`` with no kind filter), buckets by ``event``,
and renders a Hinglish paragraph.

Pure functions, no Qt — the diff skill and any dashboard consume from here.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

from core import activity_digest as _ad

log = logging.getLogger(__name__)


# Human, ordered labels for the event kinds we know about. Unknown kinds fall
# through to a generic "<kind> events" line so new emitters surface for free.
_KNOWN_ORDER = ["skill_dispatch", "routine_fire", "presence_moment"]


def changes(window_h: float = 24.0, **kw) -> dict:
    """Bucket every event in the window by kind, with light per-kind detail."""
    events = _ad.read_events(window_h, event_name=None, **kw)

    by_kind: Counter = Counter()
    intents: Counter = Counter()
    routines: Counter = Counter()
    for ev in events:
        kind = ev.get("event") or "?"
        by_kind[kind] += 1
        if kind == "skill_dispatch":
            intents[ev.get("intent") or "?"] += 1
        elif kind == "routine_fire":
            routines[ev.get("routine") or "?"] += 1

    return {
        "window_h": window_h,
        "total":    len(events),
        "by_kind":  dict(by_kind),
        "top_intents":  intents.most_common(3),
        "top_routines": routines.most_common(3),
    }


def _kinds_in_order(by_kind: dict) -> list[str]:
    known = [k for k in _KNOWN_ORDER if k in by_kind]
    extra = sorted(k for k in by_kind if k not in _KNOWN_ORDER)
    return known + extra


def summarize_changes(window_h: float = 24.0, **kw) -> str:
    """One-paragraph narrative of what AERIS did/changed in the window."""
    c = changes(window_h, **kw)
    win = _ad._fmt_window(window_h)
    if c["total"] == 0:
        return f"{win.capitalize()} mein kuch khaas nahi hua, sir — koi activity record nahi."

    by_kind = c["by_kind"]
    lines: list[str] = []
    for kind in _kinds_in_order(by_kind):
        n = by_kind[kind]
        if kind == "skill_dispatch":
            top = ", ".join(name for name, _ in c["top_intents"])
            tail = f" (top: {top})" if top else ""
            lines.append(f"{n} command{'s' if n != 1 else ''} chale{tail}")
        elif kind == "routine_fire":
            top = ", ".join(name for name, _ in c["top_routines"])
            tail = f" ({top})" if top else ""
            lines.append(f"{n} scheduled routine{'s' if n != 1 else ''} fire hui{tail}")
        elif kind == "presence_moment":
            lines.append(f"{n} presence moment{'s' if n != 1 else ''}")
        else:
            pretty = kind.replace("_", " ")
            lines.append(f"{n} {pretty} event{'s' if n != 1 else ''}")

    body = "; ".join(lines)
    return f"{win.capitalize()} mein: {body}."


def changes_since_boot(**kw) -> str:
    """Convenience: narrate everything since the most recent boot record.

    Falls back to a 24 h window if the boot marker can't be read.
    """
    window_h = 24.0
    try:
        import json
        from pathlib import Path
        boot = Path(__file__).resolve().parent.parent / "data" / "last_boot.json"
        with open(boot, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        import time
        start = data.get("start_time") or data.get("start")
        if isinstance(start, (int, float)):
            window_h = max((time.time() - start) / 3600.0, 1 / 60.0)
    except Exception:
        pass
    return summarize_changes(window_h, **kw)
