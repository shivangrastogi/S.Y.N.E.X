"""Background self-monitoring for the AERIS process.

Polls psutil on a daemon thread and:

  * keeps a ring buffer of the last N samples (RSS, CPU%, threads,
    open handles) so the logs panel / /metrics endpoint can render them
    without re-polling psutil per request;

  * detects memory pressure and broadcasts a level to subscribers so
    caches across the codebase can shrink or drop themselves before
    the OS starts paging us out.

Pressure levels
---------------
  LEVEL_OK        — RSS below ``_WARN_BYTES``
  LEVEL_WARNING   — between warn / critical → subscribers should HALVE
                    their cache sizes
  LEVEL_CRITICAL  — above ``_CRIT_BYTES`` → subscribers should CLEAR
                    every drop-able cache

Subscribers register a callable via ``subscribe(cb)``; the callback
receives the new level when (and only when) the level transitions.

Design notes
------------
* No Qt dependency — this module is imported by ``core/`` code that
  runs in non-Qt entry points (``main.py``, smoke tests).
* psutil failures degrade silently to "OK forever" so a missing /
  broken psutil never bricks AERIS.
* The sampler thread is a daemon so it never blocks process exit.
* All thresholds tunable via ``ResourceMonitor`` constructor for tests.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Iterable, Optional

log = logging.getLogger(__name__)


# ── Thresholds (bytes) ─────────────────────────────────────────────── #
# Chosen for a typical 16 GB DDR5 dev laptop: warn at 1.0 GB so caches
# trim before we approach the 1.4 GB hard ceiling at which the OS may
# start prioritising other apps' pages over ours.
_WARN_BYTES = 1_000 * 1024 * 1024
_CRIT_BYTES = 1_400 * 1024 * 1024

# Hysteresis: only DOWNgrade pressure when RSS drops noticeably below
# the threshold, otherwise we'd flap on every GC cycle.
_HYSTERESIS_BYTES = 80 * 1024 * 1024

LEVEL_OK = 0
LEVEL_WARNING = 1
LEVEL_CRITICAL = 2

_LEVEL_NAMES = {LEVEL_OK: "OK", LEVEL_WARNING: "WARNING", LEVEL_CRITICAL: "CRITICAL"}


@dataclass(frozen=True)
class ResourceSample:
    ts: float
    rss_bytes: int
    cpu_percent: float
    num_threads: int
    num_handles: int


@dataclass
class _State:
    level: int = LEVEL_OK
    samples: Deque[ResourceSample] = field(default_factory=lambda: deque(maxlen=1000))


class ResourceMonitor:
    """Single-process resource monitor — start one, share it everywhere.

    Typical wiring (from ``main_engine`` or ``main_window``):

        from core.resource_monitor import get_monitor
        mon = get_monitor()
        mon.start()
        mon.subscribe(my_cache.on_pressure)

    ``subscribe`` callbacks fire on the monitor's own daemon thread —
    keep them cheap and thread-safe (no GUI work; emit a Qt signal
    if you need to touch widgets).
    """

    def __init__(self,
                 *,
                 interval_s: float = 4.0,
                 warn_bytes: int = _WARN_BYTES,
                 crit_bytes: int = _CRIT_BYTES,
                 hysteresis_bytes: int = _HYSTERESIS_BYTES,
                 history: int = 1000):
        self._interval_s = max(0.5, interval_s)
        self._warn = warn_bytes
        self._crit = crit_bytes
        self._hyst = hysteresis_bytes
        self._state = _State(samples=deque(maxlen=history))
        self._lock = threading.RLock()
        self._subscribers: list[Callable[[int], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._proc = None
        try:
            import psutil
            self._proc = psutil.Process(os.getpid())
            # Prime cpu_percent so subsequent calls return a real delta.
            self._proc.cpu_percent(interval=None)
        except Exception as e:
            log.info("[ResourceMonitor] psutil unavailable (%s) — degraded mode.", e)

    # ── Public API ─────────────────────────────────────────────────

    def start(self) -> None:
        """Idempotent: spawns the daemon poller on first call."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="ResourceMonitor", daemon=True
            )
            self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        """Signal the poller to exit. Safe to call from any thread."""
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=timeout)

    def subscribe(self, cb: Callable[[int], None]) -> Callable[[], None]:
        """Register ``cb(level)`` for pressure-transition events.

        Returns an ``unsubscribe()`` closure for clean teardown.
        Callback fires on the monitor thread; do not touch Qt widgets
        directly — emit a queued signal instead.
        """
        with self._lock:
            self._subscribers.append(cb)
        def _off():
            with self._lock:
                try: self._subscribers.remove(cb)
                except ValueError: pass
        return _off

    def latest(self) -> Optional[ResourceSample]:
        with self._lock:
            return self._state.samples[-1] if self._state.samples else None

    def snapshot(self) -> list[ResourceSample]:
        """Copy of the ring buffer — safe to iterate from any thread."""
        with self._lock:
            return list(self._state.samples)

    def level(self) -> int:
        with self._lock:
            return self._state.level

    def level_name(self) -> str:
        return _LEVEL_NAMES.get(self.level(), "UNKNOWN")

    # ── Internals ─────────────────────────────────────────────────

    def _run(self) -> None:
        # Stagger the first sample slightly so launch-time GIL churn
        # doesn't fight the boot pipeline for the GIL.
        if self._stop.wait(0.5):
            return
        while not self._stop.is_set():
            self._sample_once()
            # Use Event.wait for cancellable sleep.
            if self._stop.wait(self._interval_s):
                return

    def _sample_once(self) -> None:
        sample = self._read_sample()
        if sample is None:
            return
        new_level = self._classify(sample.rss_bytes)
        fire: list[Callable[[int], None]] = []
        with self._lock:
            self._state.samples.append(sample)
            if new_level != self._state.level:
                old = self._state.level
                self._state.level = new_level
                fire = list(self._subscribers)
                log.info(
                    "[ResourceMonitor] pressure %s → %s (RSS=%.0f MB)",
                    _LEVEL_NAMES.get(old), _LEVEL_NAMES.get(new_level),
                    sample.rss_bytes / (1024 * 1024),
                )
        # Notify outside the lock so a slow callback doesn't block sampling.
        for cb in fire:
            try:
                cb(new_level)
            except Exception:
                log.exception("[ResourceMonitor] subscriber raised")

    def _read_sample(self) -> Optional[ResourceSample]:
        if self._proc is None:
            return None
        try:
            mem = self._proc.memory_info()
            cpu = self._proc.cpu_percent(interval=None)
            try:
                handles = self._proc.num_handles()  # Windows only
            except AttributeError:
                handles = 0
            return ResourceSample(
                ts=time.time(),
                rss_bytes=int(mem.rss),
                cpu_percent=float(cpu),
                num_threads=int(self._proc.num_threads()),
                num_handles=int(handles),
            )
        except Exception:
            return None

    def _classify(self, rss: int) -> int:
        # Hysteresis: when DOWNgrading, require RSS to drop below the
        # threshold by at least _HYSTERESIS_BYTES so we don't flap.
        current = self._state.level
        if rss >= self._crit:
            return LEVEL_CRITICAL
        if rss >= self._warn:
            if current == LEVEL_CRITICAL and rss >= self._crit - self._hyst:
                return LEVEL_CRITICAL
            return LEVEL_WARNING
        # rss below warn threshold
        if current == LEVEL_WARNING and rss >= self._warn - self._hyst:
            return LEVEL_WARNING
        if current == LEVEL_CRITICAL and rss >= self._crit - self._hyst:
            return LEVEL_CRITICAL
        return LEVEL_OK


# ── Singleton accessor ─────────────────────────────────────────────── #

_singleton: Optional[ResourceMonitor] = None
_singleton_lock = threading.Lock()


def get_monitor() -> ResourceMonitor:
    """Return the process-wide monitor, creating it if necessary."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = ResourceMonitor()
        return _singleton


# ── Smoke test ─────────────────────────────────────────────────────── #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mon = get_monitor()
    mon.subscribe(lambda lvl: print(f"  -> pressure changed to {_LEVEL_NAMES[lvl]}"))
    mon.start()
    print("Sampling every 1s for 3 ticks...")
    mon._interval_s = 1.0
    time.sleep(3.5)
    for s in mon.snapshot():
        print(f"  RSS={s.rss_bytes/(1024*1024):6.0f} MB  "
              f"CPU={s.cpu_percent:5.1f}%  threads={s.num_threads}  "
              f"handles={s.num_handles}")
    mon.stop()
