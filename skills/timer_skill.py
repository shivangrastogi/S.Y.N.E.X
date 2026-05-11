"""Lightweight countdown timer.

"5 minute timer lagao" / "set a 30 second timer" / "10 minute mein chai
yaad dilana" → schedules a non-blocking timer thread; on fire it speaks
through TTS if connected, else writes a desktop toast.

Backed by a single dict of active timers keyed by id; "list timers"
shows what's running, "cancel timer 2" stops one.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)


@dataclass
class _Timer:
    id: int
    label: str
    fire_at: datetime
    thread: threading.Thread
    cancel_evt: threading.Event


_TIMERS: dict[int, _Timer] = {}
_NEXT_ID = [1]
_LOCK = threading.RLock()


def _toast(title: str, body: str) -> None:
    """Best-effort desktop toast — falls back to print on any failure."""
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, body, duration=8, threaded=True)
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBeep(0xFFFFFFFF)
    except Exception:
        pass
    print(f"[TIMER] {title}: {body}")


_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(seconds?|second|secs?|sec|"
    r"minutes?|minute|mins?|min|hours?|hour|hrs?|hr|"
    r"ghante?|ghanta|minute|minit|sekand)?",
    re.IGNORECASE,
)


def _parse_duration(text: str) -> Optional[timedelta]:
    """Extract first duration mentioned. Defaults to minutes if unit missing."""
    if not text:
        return None
    m = _DURATION_RE.search(text)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "minute").lower()
    if unit.startswith(("sec", "sekand")):
        return timedelta(seconds=val)
    if unit.startswith(("hour", "hr", "ghan")):
        return timedelta(hours=val)
    return timedelta(minutes=val)


def _strip_duration(text: str) -> str:
    return _DURATION_RE.sub(" ", text).strip()


_LABEL_FILLER_RE = re.compile(
    r"\b(timer|set|lagao|laga|chalao|do|karo|kar|in|mein|ke|liye|"
    r"a|an|the|for|please|sir|jarvis|ek|tak|baad|after)\b",
    re.IGNORECASE,
)


def _extract_label(text: str) -> str:
    rest = _strip_duration(text)
    rest = _LABEL_FILLER_RE.sub(" ", rest)
    rest = re.sub(r"\s+", " ", rest).strip(" .,-:")
    return rest or "timer"


@skill(
    name="set_timer",
    description="Set a countdown timer that fires a desktop toast/beep.",
    patterns=[
        "set a 5 minute timer", "5 minute ka timer lagao",
        "10 minute timer chalu karo", "30 second timer set karo",
        "1 hour timer", "ek minute ka timer lagao",
        "timer set karo 15 minute", "remind me in 5 minutes",
        "5 minute mein yaad dilao", "10 minute mein chai yaad dilana",
        "timer 20 min", "set timer for 45 seconds",
        "2 ghante ka timer lagao",
    ],
    required_entities=["spec"],
    prompts={"spec": "Kitne time ka timer chahiye?"},
)
def set_timer(slots: dict) -> str:
    raw = (slots.get("spec") or slots.get("query") or "").strip()
    duration = _parse_duration(raw)
    if not duration or duration.total_seconds() <= 0:
        return "Time samajh nahi aaya — '5 minute ka timer' jaisa bolo."
    label = _extract_label(raw)
    fire_at = datetime.now() + duration

    cancel_evt = threading.Event()

    def _wait_and_fire(timer_id: int, secs: float, lbl: str):
        if cancel_evt.wait(secs):
            return  # cancelled
        _toast("AERIS Timer", f"{lbl} — time's up!")
        with _LOCK:
            _TIMERS.pop(timer_id, None)

    with _LOCK:
        tid = _NEXT_ID[0]
        _NEXT_ID[0] += 1
        t = threading.Thread(target=_wait_and_fire,
                             args=(tid, duration.total_seconds(), label),
                             daemon=True, name=f"Timer-{tid}")
        _TIMERS[tid] = _Timer(id=tid, label=label, fire_at=fire_at,
                              thread=t, cancel_evt=cancel_evt)
        t.start()

    return (f"Timer #{tid} set: {label} — "
            f"{fire_at.strftime('%I:%M:%S %p')} pe yaad dilaunga.")


@skill(
    name="list_timers",
    description="List all active timers.",
    patterns=[
        "list timers", "active timers batao",
        "konse timers chalu hain", "show running timers",
        "timer status",
    ],
    required_entities=[],
)
def list_timers(slots: dict) -> str:
    with _LOCK:
        items = sorted(_TIMERS.values(), key=lambda t: t.fire_at)
    if not items:
        return "Koi active timer nahi hai, sir."
    lines = ["Active timers:"]
    for t in items:
        remaining = (t.fire_at - datetime.now()).total_seconds()
        if remaining < 0:
            remaining = 0
        lines.append(f"  #{t.id} {t.label} — {int(remaining)}s baaki")
    return "\n".join(lines)


@skill(
    name="cancel_timer",
    description="Cancel an active timer by id, or all if 'all' is given.",
    patterns=[
        "cancel timer", "stop timer", "timer cancel karo",
        "all timers cancel karo", "cancel all timers",
        "timer hatao", "timer band karo",
    ],
    required_entities=[],
)
def cancel_timer(slots: dict) -> str:
    raw = " ".join(str(v) for v in slots.values()).lower() if slots else ""
    if not raw:
        raw = "all"
    if "all" in raw or "sab" in raw:
        with _LOCK:
            n = len(_TIMERS)
            for t in list(_TIMERS.values()):
                t.cancel_evt.set()
            _TIMERS.clear()
        return f"{n} timers cancel kar diye."
    m = re.search(r"\d+", raw)
    if not m:
        return "Konsa timer cancel karna hai? Number batao."
    tid = int(m.group(0))
    with _LOCK:
        t = _TIMERS.pop(tid, None)
    if not t:
        return f"Timer #{tid} nahi mila."
    t.cancel_evt.set()
    return f"Timer #{tid} cancel."
