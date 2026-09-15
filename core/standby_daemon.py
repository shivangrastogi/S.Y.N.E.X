"""Standby daemon — the thin, headless driver that runs the Tier-0 always-on
loop and hands control to the tiered-wake ``StandbyController``.

This is the only piece that touches the *real* services (wake detector, power
monitor, STT/TTS), so it is deliberately tiny and dumb — all the decisions live
in ``StandbyController``, which is already unit-tested. What lives here:

  * a **tick thread** (mirrors ``service_supervisor.start_monitor``'s pattern)
    that calls ``controller.tick()`` on an interval so the brain is torn down
    after idle;
  * the **wake callback** — when the wake word fires, capture speech (STT),
    hand it to the controller, and speak any reply (TTS);
  * **power wiring** — forward power-change events to the controller so a
    critical battery drops the heavy brain.

Everything is injected (controller, wake detector, power monitor, stt, tts,
sleep) so the loop body, the wake handler and the start/stop wiring are all
tested with fakes — no Vosk model, no mic, no process spawn, no real timing.
The real component construction lives in ``main.py --standby``.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from core.standby_power import (
    ES_CONTINUOUS,
    StandbyPowerPolicy,
    set_execution_state as _default_set_execution_state,
)


class StandbyDaemon:
    """Runs the always-on Tier-0 loop around a ``StandbyController``.

    Parameters
    ----------
    controller:
        A ``core.standby_runtime.StandbyController``.
    wake_detector:
        Object with ``listen_async(on_wake)`` and ``stop()`` (the real
        ``core.wake_word.WakeWordDetector``).
    power_monitor:
        Object with ``on_power_change(cb)`` (the real ``core.power_state``
        ``PowerMonitor``). May be None to skip power reactions.
    stt:
        ``() -> Optional[str]`` — capture what the user said after a wake.
    tts:
        ``(str) -> None`` — speak a reply. May be None (silent).
    tick_interval_s:
        How often the idle check runs.
    sleep:
        Injectable ``(float) -> None`` for the tick loop (tests pass a fake).
    """

    def __init__(
        self,
        *,
        controller,
        wake_detector,
        power_monitor=None,
        stt: Callable[[], Optional[str]],
        tts: Optional[Callable[[str], None]] = None,
        tick_interval_s: float = 5.0,
        sleep: Callable[[float], None] = time.sleep,
        power_policy: Optional[StandbyPowerPolicy] = None,
        set_execution_state: Callable[[int], object] = _default_set_execution_state,
        checkpoint: Optional[Callable[[], None]] = None,
        checkpoint_interval_s: float = 300.0,
        wake_observer: Optional[Callable[[], None]] = None,
        degraded_check: Optional[Callable[[], Optional[str]]] = None,
        quiet_hours=None,
        now_dt: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._controller = controller
        self._wake = wake_detector
        self._power = power_monitor
        self._stt = stt
        self._tts = tts
        # Optional observer notified on every (non-paused) wake — used to feed
        # the raw wake count into telemetry.
        self._wake_observer = wake_observer
        # Optional: when a wake produced no reply, ask this for something to say
        # (e.g. "brain unavailable" while the spin-up breaker is open) so a
        # degraded system isn't just silent.
        self._degraded_check = degraded_check

        # Optional quiet-hours window: during it, release the system-awake hold
        # so the machine can enter real sleep (big overnight power saving).
        self._quiet_hours = quiet_hours
        self._now_dt = now_dt
        self._tick_interval = float(tick_interval_s)
        self._sleep = sleep

        # Periodic checkpoint (bank the lifetime duty cycle) so an *unclean* exit
        # — reboot, power loss — loses at most one interval. Safe to call
        # repeatedly: the store's commit recomputes from a fixed baseline.
        self._checkpoint = checkpoint
        self._checkpoint_every = max(
            1, int(round(float(checkpoint_interval_s) / max(self._tick_interval, 0.001))))
        self._ticks = 0

        # Windows power policy (optional). When set, the tick thread re-asserts
        # the chosen execution-state flags — the thread is the steady owner that
        # a thread-scoped SetThreadExecutionState needs.
        self._policy = power_policy
        self._set_exec = set_execution_state
        self._exec_flags = ES_CONTINUOUS

        self._paused = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---- the wake callback (what the detector calls) ------------------ #

    def on_wake(self) -> Optional[str]:
        """Wake fired: run one turn via the controller and speak any reply."""
        if self._paused:
            return None  # listening paused — ignore even a stray wake
        if self._wake_observer is not None:
            try:
                self._wake_observer()
            except Exception:
                pass
        reply = self._controller.handle_wake(self._stt)
        # No reply may just mean "no speech"; but if the system is degraded
        # (brain can't start), say so instead of leaving the user in silence.
        speak = reply
        if not reply and self._degraded_check is not None:
            try:
                speak = self._degraded_check()
            except Exception:
                speak = None
        if speak and self._tts is not None:
            try:
                self._tts(speak)
            except Exception:
                # Speaking must never crash the always-on loop.
                pass
        return reply

    # ---- the tick loop ----------------------------------------------- #

    def _run_ticks(self) -> None:
        while not self._stop.is_set():
            try:
                self._controller.tick()
            except Exception:
                pass
            if self._policy is not None:
                self._reassert_exec()  # keep the execution-state hold alive
            self._ticks += 1
            if self._checkpoint is not None and self._ticks % self._checkpoint_every == 0:
                self._do_checkpoint()
            self._sleep(self._tick_interval)

    def _do_checkpoint(self) -> None:
        """Bank the lifetime duty cycle. Never let a bad write crash the loop."""
        try:
            self._checkpoint()
        except Exception:
            pass

    def _reassert_exec(self) -> None:
        flags = self._exec_flags
        # During quiet hours, drop the system-awake requirement so the machine
        # can sleep normally (the user is asleep; movement will wake it). This is
        # re-evaluated every tick, so it engages/releases at the window boundary.
        if self._quiet_hours is not None and self._quiet_hours.is_quiet(self._now_dt()):
            flags = ES_CONTINUOUS
        try:
            self._set_exec(flags)
        except Exception:
            pass

    def in_quiet_hours(self) -> bool:
        return (self._quiet_hours is not None
                and self._quiet_hours.is_quiet(self._now_dt()))

    def _on_power(self, on_battery: bool, percent: int, plugged: bool) -> None:
        """Power changed: let the controller react (drop the brain if critical)
        and recompute how awake we should keep the machine."""
        try:
            self._controller.on_power_change(on_battery, percent, plugged)
        except Exception:
            pass
        if self._policy is not None:
            self._exec_flags = self._policy.flags_for(on_battery, percent)

    def _on_idle(self, idle_s: int, is_idle: bool) -> None:
        """User crossed the OS input-idle threshold — forward it to the
        controller so it can retune the brain's warm-time (presence adaptive)."""
        fn = getattr(self._controller, "on_user_idle", None)
        if fn is None:
            return
        try:
            fn(is_idle)
        except Exception:
            pass

    # ---- lifecycle --------------------------------------------------- #

    def start(self) -> None:
        """Wire power events, start listening for the wake word, and start the
        idle-tick thread. Non-blocking — the process then just lives."""
        if self._power is not None:
            self._power.on_power_change(self._on_power)
            # Presence-adaptive warm-time: retune on OS input-idle transitions.
            if hasattr(self._power, "on_idle_change"):
                self._power.on_idle_change(self._on_idle)
        self._wake.listen_async(self.on_wake)

        # Set the initial execution-state hold from the current power situation.
        if self._policy is not None:
            on_battery, percent = False, 100
            if self._power is not None and hasattr(self._power, "snapshot"):
                try:
                    snap = self._power.snapshot()
                    on_battery, percent = snap.on_battery, snap.percent
                except Exception:
                    pass
            self._exec_flags = self._policy.flags_for(on_battery, percent)
            self._reassert_exec()

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_ticks, name="aeris-standby-tick", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the tick loop and the wake detector, and release any power hold
        (so the machine is free to sleep normally once standby ends)."""
        self._stop.set()
        try:
            self._wake.stop()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        if self._policy is not None:
            try:
                self._set_exec(ES_CONTINUOUS)  # clear all keep-awake requirements
            except Exception:
                pass

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- control surface (bound by the tray / status UI) ------------- #

    def pause_listening(self) -> None:
        """Stop reacting to the wake word (e.g. during a meeting)."""
        self._paused = True
        try:
            self._wake.pause()
        except Exception:
            pass

    def resume_listening(self) -> None:
        self._paused = False
        try:
            self._wake.resume()
        except Exception:
            pass

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def brain_state(self):
        """Current brain power state (StandbyState) from the controller."""
        return self._controller.state
