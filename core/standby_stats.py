"""Standby telemetry — the duty cycle that proves the power win over time.

A one-off memory snapshot (``power_report``) shows the *depth* of the saving;
this shows the *duration* of it: across a whole session, how much of the time
was the brain actually dormant? A healthy always-on assistant is dormant ~99% of
the time and only flickers to ACTIVE for the seconds around a real conversation.

``StandbyStats`` is driven by the same ``on_state_change`` callback the
orchestrator already emits (DORMANT ⇄ ACTIVE), plus ``on_wake`` for a raw wake
count. It is pure accounting with an injected clock, so every number is
unit-tested without any real timing.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from core.standby_orchestrator import StandbyState


class StandbyStats:
    """Accumulates time-in-state and event counts for a standby session.

    Thread-safe: ``on_state_change`` is called from the wake/power threads while
    the periodic checkpoint and the tray status read ``snapshot`` from other
    threads, so all state access is guarded by a single lock.
    """

    def __init__(self, *, now: Callable[[], float] = time.monotonic,
                 initial: StandbyState = StandbyState.DORMANT) -> None:
        self._now = now
        self._start = now()
        self._state = initial
        self._state_since = self._start
        self._active_s = 0.0
        self._dormant_s = 0.0
        self._wakes = 0
        self._spinups = 0  # DORMANT → ACTIVE transitions
        self._lock = threading.Lock()

    def on_wake(self) -> None:
        """Count a wake word firing (whether or not it spun the brain up)."""
        with self._lock:
            self._wakes += 1

    def on_state_change(self, state: StandbyState) -> None:
        """Bank the time spent in the state we're leaving, then switch."""
        with self._lock:
            now = self._now()
            elapsed = now - self._state_since
            if self._state is StandbyState.ACTIVE:
                self._active_s += elapsed
            else:
                self._dormant_s += elapsed
            if state is StandbyState.ACTIVE and self._state is not StandbyState.ACTIVE:
                self._spinups += 1
            self._state = state
            self._state_since = now

    def snapshot(self) -> dict:
        """Current totals, including the in-progress state segment."""
        with self._lock:
            now = self._now()
            elapsed = now - self._state_since
            active = self._active_s + (elapsed if self._state is StandbyState.ACTIVE else 0.0)
            dormant = self._dormant_s + (elapsed if self._state is not StandbyState.ACTIVE else 0.0)
            wakes = self._wakes
            spinups = self._spinups
            start = self._start
        total = active + dormant
        dormant_pct = (dormant / total * 100.0) if total > 0 else 100.0
        avg_active = (active / spinups) if spinups > 0 else 0.0
        return {
            "uptime_s": round(now - start, 1),
            "active_s": round(active, 1),
            "dormant_s": round(dormant, 1),
            "dormant_pct": round(dormant_pct, 1),
            "wakes": wakes,
            "spinups": spinups,
            "avg_active_s": round(avg_active, 1),
        }

    def summary_line(self) -> str:
        s = self.snapshot()
        return (f"brain dormant {s['dormant_pct']:.0f}% of {s['uptime_s']:.0f}s "
                f"· {s['spinups']} spin-ups · {s['wakes']} wakes")
