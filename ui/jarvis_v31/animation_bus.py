"""Shared animation timer for all JARVIS v3.1 widgets.

Before this module existed, every animated widget owned its own QTimer:
  - ReactorRings, _WireLayer:      16 ms (60 FPS)
  - ParticleField:                 60 ms
  - 12+ small blink/pulse widgets: 60 ms each

That meant 15+ separate timers firing on the GUI thread, each waking
the event loop, calling time.monotonic(), and triggering paint events.
The cumulative cost left almost no headroom for input events, which is
why Windows' "Not Responding" dialog appeared on a single click.

This module consolidates all of that into ONE master timer with two
signals fanned out from it:

  tick_fast  — every 33 ms (≈30 FPS).  For heavy paint widgets:
               ReactorRings, _WireLayer, ParticleField.
  tick_slow  — every 66 ms (≈15 FPS).  For small blink/pulse widgets
               (dots, pills, status indicators) — visually identical
               to 60 ms but cuts paint count in half.

Widgets read `bus.now_ms` to get the current animation time. They no
longer need their own `time.monotonic()` calls per paintEvent.

Cleanup is automatic: Qt disconnects slots when the receiver QObject is
destroyed, so connecting `bus.tick_slow.connect(self.update)` does not
leak when the widget is removed from the tree.
"""
from __future__ import annotations

import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


class AnimationBus(QObject):
    """One QTimer driving every animated widget in the app."""

    tick_fast = pyqtSignal()   # ~30 FPS  (33 ms interval)
    tick_slow = pyqtSignal()   # ~15 FPS  (every other fast tick)

    # Master interval — the only place this should ever be tuned.
    # 33 ms = 30 FPS at AC, raised to 66 ms (15 FPS) on battery / when
    # the user is idle. set_interval() runtime-tunable.
    _INTERVAL_MS_AC = 33
    _INTERVAL_MS_BATTERY = 66

    def __init__(self):
        super().__init__()
        self._start = time.monotonic()
        self.now_ms: float = 0.0      # ms since bus init — read this in paintEvent
        self._frame = 0
        self._interval_ms = self._INTERVAL_MS_AC
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self._interval_ms)

    def set_interval(self, ms: int) -> None:
        """Runtime-tunable tick interval. Used by power/idle adapter to
        drop FPS to 15 on battery, restore to 30 on AC."""
        ms = max(15, min(200, int(ms)))
        self._interval_ms = ms
        if self._timer.isActive():
            self._timer.start(ms)

    def use_battery_profile(self) -> None:
        self.set_interval(self._INTERVAL_MS_BATTERY)

    def use_ac_profile(self) -> None:
        self.set_interval(self._INTERVAL_MS_AC)

    def _on_tick(self) -> None:
        # Single time.monotonic() shared by every animated widget this frame.
        self.now_ms = (time.monotonic() - self._start) * 1000.0
        self.tick_fast.emit()
        self._frame += 1
        if self._frame % 2 == 0:
            self.tick_slow.emit()

    # ------------------------------------------------------------------ #
    #  Boot-time pause / resume                                           #
    # ------------------------------------------------------------------ #
    #  While the brain is loading sentence_transformers / spaCy, the GUI #
    #  thread is fighting the brain thread for the GIL. Pausing the bus  #
    #  during boot eliminates ~30 paint events / second of contention.   #

    def pause(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def resume(self) -> None:
        if not self._timer.isActive():
            self._timer.start(self._interval_ms)


_instance: AnimationBus | None = None


def get_bus() -> AnimationBus:
    """Lazy singleton accessor. Safe to call before/after QApplication.

    The bus is created on first call. Because QObject creation requires a
    running QApplication, callers must invoke this only AFTER QApplication
    is constructed — which in practice means from inside widget __init__
    methods, never at module import time.
    """
    global _instance
    if _instance is None:
        _instance = AnimationBus()
    return _instance
