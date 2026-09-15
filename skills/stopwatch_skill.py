"""Count-up stopwatch by voice — start, lap, stop. Session-local, no network.

Separate from the countdown timers (set_timer/quick_timer) — a stopwatch
counts UP from when you say start.
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="stopwatch_start",
    description="Start a count-up stopwatch (local).",
    patterns=[
        "stopwatch start karo", "stopwatch chalu karo", "stopwatch shuru karo",
        "start the stopwatch", "time count karna shuru karo",
        "stopwatch on karo", "ginna shuru karo time",
    ],
    required_entities=[],
)
def stopwatch_start(_slots: dict) -> str:
    from core.stopwatch import get_stopwatch
    sw = get_stopwatch()
    if sw.start():
        return "Stopwatch chalu — 'stopwatch stop karo' bolke rok dena, sir."
    from core.stopwatch import fmt_elapsed
    return (f"Stopwatch pehle se chal raha hai ({fmt_elapsed(sw.elapsed())}). "
            "'stopwatch kitna hua' ya 'stopwatch stop karo' bolo.")


@skill(
    name="stopwatch_check",
    description="Check the running stopwatch / record a lap (local).",
    patterns=[
        "stopwatch kitna hua", "stopwatch time batao", "lap time",
        "kitna time hua stopwatch me", "lap mark karo",
        "stopwatch pe kitna time", "abhi tak kitna time hua",
    ],
    required_entities=[],
)
def stopwatch_check(_slots: dict) -> str:
    from core.stopwatch import get_stopwatch, fmt_elapsed
    sw = get_stopwatch()
    lap = sw.lap()
    if lap is None:
        return "Stopwatch chal hi nahi raha, sir — 'stopwatch start karo'."
    total, since = lap
    return f"Stopwatch: {fmt_elapsed(total)} (is lap: {fmt_elapsed(since)})."


@skill(
    name="stopwatch_stop",
    description="Stop the stopwatch and report the final time (local).",
    patterns=[
        "stopwatch stop karo", "stopwatch band karo", "stopwatch rok do",
        "stop the stopwatch", "stopwatch off karo", "time ginna band karo",
    ],
    required_entities=[],
)
def stopwatch_stop(_slots: dict) -> str:
    from core.stopwatch import get_stopwatch, fmt_elapsed
    total = get_stopwatch().stop()
    if total is None:
        return "Stopwatch chal hi nahi raha tha, sir."
    return f"Stopwatch rok diya — total {fmt_elapsed(total)}."
