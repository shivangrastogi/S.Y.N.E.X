"""Frame-rate policy for the animation bus — deliberately Qt-free.

Two independent questions decide how often the reactor and particle field
repaint:

* **power**  — how expensive are we allowed to be? (AC vs battery)
* **idle**   — is anyone actually watching?

They compose rather than override: waking from idle on battery returns to the
battery rate, not to AC. Keeping that state machine here, apart from
``AnimationBus``, buys two things —

1. it is testable without standing up a ``QApplication``; and
2. **it keeps PyQt5 out of the test process.** On this machine torch and Qt
   fight over DLL init (`WinError 1114`, see CLAUDE.md "Boot order is
   load-bearing"): whichever loads second can fail. Test files are collected
   alphabetically, so a test importing PyQt5 from a file sorting before
   `test_incremental_training.py` pulls Qt in ahead of torch and breaks
   collection for the whole suite. That is not hypothetical — it happened.
   Import this module from tests, never ``animation_bus``.
"""
from __future__ import annotations

import time


def should_be_idle(now: float, last_activity: float, idle_after_s: float) -> bool:
    """Has the user been away long enough to drop to the idle frame rate?

    ``idle_after_s <= 0`` disables idling. A ``last_activity`` in the future —
    a clock jump, or wall-clock handed to a monotonic-based caller — reads as
    "just now" rather than as an enormous idle span.
    """
    if idle_after_s <= 0:
        return False
    return (now - last_activity) >= idle_after_s


class FrameRatePolicy:
    """Tracks the power profile + idleness and yields one interval."""

    def __init__(self, ac_ms: int, battery_ms: int, idle_ms: int,
                 idle_after_s: float):
        self.ac_ms = ac_ms
        self.battery_ms = battery_ms
        self.idle_ms = idle_ms
        self.idle_after_s = idle_after_s
        self._base_ms = ac_ms
        self._idle = False
        self._last_activity = time.monotonic()

    @property
    def is_idle(self) -> bool:
        return self._idle

    @property
    def interval_ms(self) -> int:
        """The interval the timer should currently be running at."""
        return self.idle_ms if self._idle else self._base_ms

    def use_ac(self) -> int:
        self._base_ms = self.ac_ms
        return self.interval_ms

    def use_battery(self) -> int:
        self._base_ms = self.battery_ms
        return self.interval_ms

    def note_activity(self, now: float | None = None) -> int:
        """Record an interaction; leaves idle immediately if we were idle."""
        self._last_activity = time.monotonic() if now is None else now
        self._idle = False
        return self.interval_ms

    def check_idle(self, now: float | None = None) -> int:
        """Re-evaluate idleness and return the interval to run at."""
        now = time.monotonic() if now is None else now
        self._idle = should_be_idle(now, self._last_activity, self.idle_after_s)
        return self.interval_ms
