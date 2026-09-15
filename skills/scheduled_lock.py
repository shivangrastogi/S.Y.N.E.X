"""Schedule a lock-screen for some time in the future.

  * ``lock_after``  — "lock in 5 minutes" / "lock after 2 mins"
  * ``cancel_lock`` — abort a pending scheduled lock

Implementation uses ``threading.Timer`` so it survives across the brain
thread without needing the cron / automation engine. At most one pending
lock at a time — a new ``lock_after`` replaces the previous one.
"""
from __future__ import annotations

import ctypes
import logging
import re
import threading
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_LOCK = threading.RLock()
_TIMER: Optional[threading.Timer] = None
_FIRES_AT: float = 0.0


_INTERVAL_RE = re.compile(
    r"(?:in|after|me|mein|baad)\s+(\d+)\s*"
    r"(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|min|minute|hour|second)?",
    re.IGNORECASE,
)


def _parse_seconds(text: str) -> int:
    """Pull '5 minutes' / '2 hours' / '30s' out of ``text``. Defaults to 5 min
    if nothing parseable found."""
    if not text:
        return 5 * 60
    m = _INTERVAL_RE.search(text)
    if not m:
        # Bare number — assume minutes.
        m2 = re.search(r"\b(\d+)\b", text)
        if m2:
            return max(5, int(m2.group(1)) * 60)
        return 5 * 60
    n = int(m.group(1))
    unit = (m.group(2) or "minutes").lower()
    if unit.startswith(("s", "sec")):
        return max(5, n)
    if unit.startswith(("h", "hr")):
        return n * 3600
    return n * 60


def _do_lock() -> None:
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception as e:
        log.warning("[scheduled_lock] LockWorkStation failed: %s", e)


def _cancel_pending() -> bool:
    global _TIMER, _FIRES_AT
    with _LOCK:
        if _TIMER is None:
            return False
        try:
            _TIMER.cancel()
        except Exception:
            pass
        _TIMER = None
        _FIRES_AT = 0.0
        return True


def _schedule(seconds: int) -> None:
    global _TIMER, _FIRES_AT
    with _LOCK:
        if _TIMER is not None:
            try:
                _TIMER.cancel()
            except Exception:
                pass
        _TIMER = threading.Timer(seconds, _do_lock)
        _TIMER.daemon = True
        _TIMER.start()
        _FIRES_AT = time.monotonic() + seconds


@skill(
    name="lock_after",
    description="Schedule a lock-screen N minutes from now (default 5 min). "
                "Replaces any previously scheduled lock.",
    patterns=[
        "lock after", "lock in", "lock screen after",
        "lock me in", "screen lock after",
        "5 minute me lock karo", "2 minute mein lock karo",
        "lock kar dena", "lock after 5 min", "lock after 10 minutes",
        "lock pc in 5 minutes", "schedule lock", "auto lock",
        "lock my screen in", "lock the pc after",
    ],
    required_entities=[],
)
def lock_after(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    seconds = _parse_seconds(text)
    _schedule(seconds)
    mins = seconds // 60
    rem = seconds % 60
    if mins and rem:
        when = f"{mins}m {rem}s"
    elif mins:
        when = f"{mins} minute(s)"
    else:
        when = f"{seconds}s"
    return f"Screen lock {when} mein scheduled. 'cancel lock' bolo to abort."


@skill(
    name="cancel_lock",
    description="Cancel a pending scheduled lock (from lock_after).",
    patterns=[
        "cancel lock", "lock cancel karo", "abort lock",
        "stop lock", "lock mat karo", "scheduled lock cancel",
        "don't lock", "lock cancel",
    ],
    required_entities=[],
)
def cancel_lock(_slots: dict) -> str:
    with _LOCK:
        if _TIMER is None:
            return "Koi pending lock nahi hai."
    cancelled = _cancel_pending()
    return "Lock cancel kar diya." if cancelled else "Koi pending lock nahi hai."


@skill(
    name="lock_status",
    description="Report how long until the scheduled lock fires.",
    patterns=[
        "lock status", "lock kab hoga", "when will it lock",
        "pending lock", "is lock scheduled",
    ],
    required_entities=[],
)
def lock_status(_slots: dict) -> str:
    with _LOCK:
        if _TIMER is None:
            return "Koi pending lock nahi hai."
        remaining = max(0, int(_FIRES_AT - time.monotonic()))
    return f"Screen approx {remaining}s ({remaining // 60}m {remaining % 60}s) mein lock hoga."
