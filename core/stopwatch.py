"""Count-up stopwatch — session-local, pure stdlib.

Distinct from the countdown timers (set_timer / quick_timer): a stopwatch
measures elapsed time from when you say "start". In-memory by design — a
stopwatch that survived a restart would be meaningless.
"""
from __future__ import annotations

import threading
import time
from typing import Optional


def fmt_elapsed(secs: float) -> str:
    secs = int(round(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class Stopwatch:
    def __init__(self, *, now_fn=time.monotonic):
        self._now = now_fn
        self._start: Optional[float] = None
        self._laps: list[float] = []
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._start is not None

    def start(self) -> bool:
        """Begin timing. Returns False if already running (kept running)."""
        with self._lock:
            if self._start is not None:
                return False
            self._start = self._now()
            self._laps = []
            return True

    def elapsed(self) -> Optional[float]:
        with self._lock:
            if self._start is None:
                return None
            return self._now() - self._start

    def lap(self) -> Optional[tuple[float, float]]:
        """Record a lap. Returns (total_elapsed, since_last_lap) or None."""
        with self._lock:
            if self._start is None:
                return None
            total = self._now() - self._start
            prev = self._laps[-1] if self._laps else 0.0
            self._laps.append(total)
            return total, total - prev

    def stop(self) -> Optional[float]:
        """Stop and return final elapsed seconds, or None if not running."""
        with self._lock:
            if self._start is None:
                return None
            total = self._now() - self._start
            self._start = None
            self._laps = []
            return total


_SW: Optional[Stopwatch] = None
_SW_LOCK = threading.Lock()


def get_stopwatch() -> Stopwatch:
    global _SW
    with _SW_LOCK:
        if _SW is None:
            _SW = Stopwatch()
        return _SW
