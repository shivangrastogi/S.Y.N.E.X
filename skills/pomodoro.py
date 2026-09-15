"""Built-in Pomodoro timer — work / break cycles.

Differs from existing ``timer_set`` (one-shot reminder) by tracking a
specific work/break cadence with auto-progression:

  work 25m → break 5m → work 25m → break 5m → … → after 4 cycles, long break 15m

Skills:
  * ``pomodoro_start`` — begin (optional "for N minutes" to override default)
  * ``pomodoro_status`` — what phase, how much time left
  * ``pomodoro_stop`` — abort the current session

Uses ``threading.Timer`` (no event loop required) and posts a Win10 toast
via ``win10toast`` if available; falls back to a console message.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_DEFAULT_WORK_MIN = 25
_DEFAULT_BREAK_MIN = 5
_DEFAULT_LONG_BREAK_MIN = 15
_LONG_BREAK_AFTER = 4


_LOCK = threading.RLock()
_TIMER: Optional[threading.Timer] = None
_STATE: dict = {
    "phase": None,             # "work" | "short_break" | "long_break" | None
    "phase_ends_at": 0.0,      # monotonic
    "completed_cycles": 0,     # number of finished work blocks
    "work_min": _DEFAULT_WORK_MIN,
    "break_min": _DEFAULT_BREAK_MIN,
    "long_break_min": _DEFAULT_LONG_BREAK_MIN,
}


def _toast(title: str, msg: str) -> None:
    try:
        from win10toast import ToastNotifier  # type: ignore
        ToastNotifier().show_toast(title, msg, duration=6, threaded=True)
    except Exception:
        log.info("[pomodoro] %s — %s", title, msg)


def _strip_phase_timer() -> None:
    """Cancel + clear the currently-running phase timer."""
    global _TIMER
    with _LOCK:
        if _TIMER is not None:
            try:
                _TIMER.cancel()
            except Exception:
                pass
            _TIMER = None


def _schedule_phase(phase: str, minutes: int) -> None:
    """Start phase ``phase`` for ``minutes`` and queue the next transition."""
    global _TIMER
    seconds = max(1, int(minutes * 60))
    with _LOCK:
        _STATE["phase"] = phase
        _STATE["phase_ends_at"] = time.monotonic() + seconds
        _strip_phase_timer()
        _TIMER = threading.Timer(seconds, _on_phase_end)
        _TIMER.daemon = True
        _TIMER.start()


def _on_phase_end() -> None:
    """Fired by the timer when the current phase elapses."""
    with _LOCK:
        cur = _STATE.get("phase")
        cycles = int(_STATE.get("completed_cycles", 0))
        work_m = int(_STATE.get("work_min") or _DEFAULT_WORK_MIN)
        brk_m  = int(_STATE.get("break_min") or _DEFAULT_BREAK_MIN)
        long_m = int(_STATE.get("long_break_min") or _DEFAULT_LONG_BREAK_MIN)

    if cur == "work":
        cycles += 1
        with _LOCK:
            _STATE["completed_cycles"] = cycles
        if cycles > 0 and cycles % _LONG_BREAK_AFTER == 0:
            _toast("Pomodoro — long break",
                   f"{cycles} cycles done. Take a {long_m}-min break.")
            _schedule_phase("long_break", long_m)
        else:
            _toast("Pomodoro — break",
                   f"Work {work_m} m done. {brk_m}-min break starting.")
            _schedule_phase("short_break", brk_m)
    elif cur in ("short_break", "long_break"):
        _toast("Pomodoro — back to work",
               f"Break over. Starting next {work_m}-min work block.")
        _schedule_phase("work", work_m)
    else:
        # No phase set; nothing to do.
        return


def _parse_minutes(text: str, default: int) -> int:
    if not text:
        return default
    m = re.search(r"(?:for|of|me|mein)\s+(\d+)\s*(min|mins|minutes?|m)?", text, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)))
    # Bare integer
    m2 = re.search(r"\b(\d+)\b", text)
    if m2:
        return max(1, int(m2.group(1)))
    return default


# ── pomodoro_start ─────────────────────────────────────────────────


@skill(
    name="pomodoro_start",
    description="Start a Pomodoro session (default 25-min work + 5-min breaks; "
                "long 15-min break every 4th cycle).",
    patterns=[
        "start pomodoro", "pomodoro start karo", "begin pomodoro",
        "pomodoro chalu karo", "start a pomodoro",
        "pomodoro for 30 minutes", "25 minute pomodoro",
        "pomodoro chalao", "pomo start",
        "kick off pomodoro", "pomodoro shuru karo",
    ],
    required_entities=[],
)
def pomodoro_start(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    work_m = _parse_minutes(text, _DEFAULT_WORK_MIN)
    with _LOCK:
        _STATE["work_min"] = work_m
        _STATE["completed_cycles"] = 0
    _schedule_phase("work", work_m)
    return (f"Pomodoro start — {work_m}-min work block. "
            f"Break {_DEFAULT_BREAK_MIN} min, long break {_DEFAULT_LONG_BREAK_MIN} min "
            f"after {_LONG_BREAK_AFTER} cycles. 'pomodoro status' anytime, "
            f"'pomodoro stop' to abort.")


# ── pomodoro_status ────────────────────────────────────────────────


@skill(
    name="pomodoro_status",
    description="Report current pomodoro phase + time remaining.",
    patterns=[
        "pomodoro status", "pomodoro kahan tak", "pomodoro time left",
        "kitna time bacha pomodoro", "current pomodoro",
        "pomodoro update", "pomodoro check",
    ],
    required_entities=[],
)
def pomodoro_status(_slots: dict) -> str:
    with _LOCK:
        phase = _STATE.get("phase")
        ends = float(_STATE.get("phase_ends_at") or 0.0)
        cycles = int(_STATE.get("completed_cycles", 0))
    if phase is None:
        return "Koi pomodoro chal raha nahi. 'start pomodoro' bolo."
    remaining = max(0, int(ends - time.monotonic()))
    m, s = divmod(remaining, 60)
    label = {"work": "working", "short_break": "short break", "long_break": "long break"}[phase]
    return f"Pomodoro: {label} · {m}m {s}s left · {cycles} cycle(s) done."


# ── pomodoro_stop ──────────────────────────────────────────────────


@skill(
    name="pomodoro_stop",
    description="Stop the current pomodoro session.",
    patterns=[
        "stop pomodoro", "pomodoro stop karo", "cancel pomodoro",
        "pomodoro band karo", "end pomodoro", "abort pomodoro",
        "pomodoro khatam karo",
    ],
    required_entities=[],
)
def pomodoro_stop(_slots: dict) -> str:
    with _LOCK:
        if _STATE.get("phase") is None:
            return "Koi pomodoro chal raha nahi tha."
        cycles = int(_STATE.get("completed_cycles", 0))
        _STATE["phase"] = None
        _STATE["phase_ends_at"] = 0.0
    _strip_phase_timer()
    return f"Pomodoro stopped. {cycles} cycle(s) completed."
