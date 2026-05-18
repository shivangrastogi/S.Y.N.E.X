"""Battery + idle-time monitor — drives adaptive behaviour across AERIS.

Two signals are produced:

  * ``power_changed(on_battery: bool, percent: int, plugged: bool)`` —
    fires on every transition between AC and battery power and on
    significant battery-percent changes (>= 5 %).
  * ``idle_changed(idle_s: int, is_idle: bool)`` — fires when the user
    crosses the idle threshold (default 5 min of no input).

Subscribers tune themselves to the new state. Typical reactions:

  * AnimationBus  → drop tick_fast from 30 → 15 FPS on battery / idle.
  * ResourceMonitor → raise poll interval 4 s → 8 s on battery.
  * VoiceWorker   → suspend wake-word listener when idle.
  * BrainWorker   → defer optional caches / pre-fetches on battery.

Implementation notes
--------------------
* psutil.sensors_battery() returns None on desktops or unsupported
  hardware → we treat as "always plugged in" so nothing degrades.
* Windows idle time comes from GetLastInputInfo (user32). Reads in
  ~10 µs so we can poll every few seconds without overhead.
* All polling happens on a single daemon thread shared with the
  resource monitor's cadence to keep the wake-up profile tight.
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


# ── Tunables ───────────────────────────────────────────────────────── #

_POLL_INTERVAL_S = 6.0
_BATTERY_DELTA_REPORT = 5      # only fire on >= 5% change to avoid noise
_IDLE_THRESHOLD_S = 5 * 60     # 5 min of zero input = "idle"


@dataclass(frozen=True)
class PowerSnapshot:
    on_battery: bool
    percent: int
    plugged: bool
    idle_s: int
    is_idle: bool


class PowerMonitor:
    """Background sampler. ``get_monitor()`` returns the process-wide
    instance; tests can instantiate freely.
    """

    def __init__(self,
                 *,
                 poll_interval_s: float = _POLL_INTERVAL_S,
                 idle_threshold_s: int = _IDLE_THRESHOLD_S):
        self._poll = max(1.0, poll_interval_s)
        self._idle_threshold = max(30, idle_threshold_s)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Last-reported (so we only fire on transitions).
        self._last_on_battery: Optional[bool] = None
        self._last_pct_reported: Optional[int] = None
        self._last_is_idle: Optional[bool] = None

        # Latest snapshot (always populated post-start).
        self._snapshot = PowerSnapshot(
            on_battery=False, percent=100, plugged=True,
            idle_s=0, is_idle=False,
        )

        self._power_subs: list[Callable[[bool, int, bool], None]] = []
        self._idle_subs: list[Callable[[int, bool], None]] = []

    # ── Lifecycle ───────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="PowerMonitor", daemon=True
            )
            self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)

    # ── Subscriptions ──────────────────────────────────────────────

    def on_power_change(self, cb: Callable[[bool, int, bool], None]
                        ) -> Callable[[], None]:
        with self._lock:
            self._power_subs.append(cb)
        def _off():
            with self._lock:
                try: self._power_subs.remove(cb)
                except ValueError: pass
        return _off

    def on_idle_change(self, cb: Callable[[int, bool], None]
                       ) -> Callable[[], None]:
        with self._lock:
            self._idle_subs.append(cb)
        def _off():
            with self._lock:
                try: self._idle_subs.remove(cb)
                except ValueError: pass
        return _off

    def snapshot(self) -> PowerSnapshot:
        with self._lock:
            return self._snapshot

    # ── Internals ──────────────────────────────────────────────────

    def _run(self) -> None:
        # Tiny stagger to avoid colliding with launch-time GIL churn.
        if self._stop.wait(0.8):
            return
        while not self._stop.is_set():
            self._sample_once()
            if self._stop.wait(self._poll):
                return

    def _sample_once(self) -> None:
        bat = self._read_battery()
        idle = self._read_idle_seconds()
        is_idle = idle >= self._idle_threshold

        with self._lock:
            self._snapshot = PowerSnapshot(
                on_battery=bat[0], percent=bat[1], plugged=bat[2],
                idle_s=idle, is_idle=is_idle,
            )

            # Power transitions
            power_fire = []
            if self._last_on_battery is None or bat[0] != self._last_on_battery:
                power_fire = list(self._power_subs)
                self._last_on_battery = bat[0]
                self._last_pct_reported = bat[1]
            elif (self._last_pct_reported is None
                  or abs(bat[1] - self._last_pct_reported) >= _BATTERY_DELTA_REPORT):
                power_fire = list(self._power_subs)
                self._last_pct_reported = bat[1]

            # Idle transitions (only the cross-threshold edges, not every poll)
            idle_fire = []
            if self._last_is_idle is None or is_idle != self._last_is_idle:
                idle_fire = list(self._idle_subs)
                self._last_is_idle = is_idle

        for cb in power_fire:
            try: cb(bat[0], bat[1], bat[2])
            except Exception: log.exception("[PowerMonitor] power sub raised")
        for cb in idle_fire:
            try: cb(idle, is_idle)
            except Exception: log.exception("[PowerMonitor] idle sub raised")

    def _read_battery(self) -> tuple[bool, int, bool]:
        """Returns (on_battery, percent, plugged_in)."""
        try:
            import psutil
            b = psutil.sensors_battery()
            if b is None:
                return (False, 100, True)
            return (not b.power_plugged, int(b.percent), bool(b.power_plugged))
        except Exception:
            return (False, 100, True)

    def _read_idle_seconds(self) -> int:
        """Seconds since last keyboard/mouse input. Falls back to 0 when
        the host doesn't expose user-input idle time.
        """
        if sys.platform == "win32":
            return _win_idle_seconds()
        return 0


# ── Windows idle-time via GetLastInputInfo ─────────────────────────── #

class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.c_uint)]


def _win_idle_seconds() -> int:
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(lii)
        user32 = ctypes.WinDLL("user32")
        if not user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0
        # GetTickCount wraps every ~49 days — we treat the modular delta
        # as the idle period; wrap-around is harmless at our resolution.
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetTickCount.restype = ctypes.c_uint
        now = kernel32.GetTickCount()
        delta_ms = (now - lii.dwTime) & 0xFFFFFFFF
        return delta_ms // 1000
    except Exception:
        return 0


# ── Singleton ──────────────────────────────────────────────────────── #

_singleton: Optional[PowerMonitor] = None
_singleton_lock = threading.Lock()


def get_monitor() -> PowerMonitor:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = PowerMonitor()
        return _singleton


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mon = get_monitor()
    mon._poll = 1.0
    mon._idle_threshold = 3   # 3s for the demo
    mon.on_power_change(lambda ob, pct, pl: print(
        f"  power: on_battery={ob} pct={pct} plugged={pl}"))
    mon.on_idle_change(lambda s, idle: print(
        f"  idle: {s}s (is_idle={idle})"))
    mon.start()
    print("Sampling for 6s... stay perfectly still for >3s to trigger idle.")
    for _ in range(6):
        time.sleep(1)
        s = mon.snapshot()
        print(f"  snap on_battery={s.on_battery} pct={s.percent} idle={s.idle_s}s")
    mon.stop()
