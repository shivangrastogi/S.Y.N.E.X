"""Standby Orchestrator — the tiered-wake power core of the always-on AERIS.

This is the keystone that turns AERIS from "one heavy process that is always
resident" into an assistant that can genuinely stand by 24/7 while sipping
power (docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md → the always-on tier).

## The problem it solves

``main.py --wake`` today loads the *full* brain (torch + encoder + spaCy +
skills, ~1.5-2 GB) up front and keeps it resident; the wake word only gates
*dispatching* a turn, not *loading* the brain. So "always on" also means
"always heavy". That is the opposite of low power.

## The tiered-wake fix

Split the runtime into two power tiers and only keep the tiny one awake:

    Tier 0  (ALWAYS ON, milliwatts-ish)   Tier 2  (ON DEMAND, heavy)
    ─────────────────────────────────    ────────────────────────────
    Vosk wake-word detector  ~3-5% CPU    the full Brain service
    power/idle monitor                     (torch + encoder + skills)
    presence heartbeat                     spawned only when needed,
                                           torn down after idle.

The orchestrator owns that transition. During ``DORMANT`` the heavy brain is
**not spawned at all** (zero RSS, zero GIL, nothing to page out). On a wake it
spins the brain up (via the existing ``service_supervisor``), stays ``ACTIVE``
while there is conversation, and — after a quiet ``idle_timeout`` — spins the
brain back down and returns to ``DORMANT``.

## Design (matches the rest of the split architecture)

Deterministic and injection-based, exactly like ``service_supervisor`` and
``brain_service``: the brain lifecycle is two injected callables (``spin_up`` /
``spin_down``), the clock is injected, and the idle check is a single
``tick()`` that the real monitor thread calls on an interval AND that tests
call directly — so every transition is unit-tested with fakes, no model load
and no spawn, while the real wiring is a thin adapter.
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Callable, Optional


class StandbyState(Enum):
    """Which power tier is live right now."""

    #: Tier-0 only. The heavy brain is NOT running. Wake listener + power
    #: monitor + presence heartbeat are all that is awake.
    DORMANT = "dormant"

    #: Tier-2 live. The brain service is spun up and handling turns.
    ACTIVE = "active"


class StandbyOrchestrator:
    """Drives the DORMANT ⇄ ACTIVE transition around the heavy brain service.

    Parameters
    ----------
    spin_up:
        ``() -> bool`` — bring the brain service up. Returns whether it came up
        (a spawn can fail; then we stay DORMANT). Real wiring: start the Brain
        service via ``service_supervisor``. Tests: a fake that records calls.
    spin_down:
        ``() -> None`` — tear the brain service down (free the native heap).
    idle_timeout_s:
        Seconds of no activity in ACTIVE before the brain is spun back down.
    now:
        Monotonic clock, injectable for tests. Defaults to ``time.monotonic``.
    on_state_change:
        Optional ``(StandbyState) -> None`` callback for UI / logging.
    """

    def __init__(
        self,
        *,
        spin_up: Callable[[], bool],
        spin_down: Callable[[], None],
        idle_timeout_s: float = 180.0,
        now: Callable[[], float] = time.monotonic,
        on_state_change: Optional[Callable[["StandbyState"], None]] = None,
    ) -> None:
        self._spin_up = spin_up
        self._spin_down = spin_down
        self._idle_timeout_s = float(idle_timeout_s)
        self._now = now
        self._on_state_change = on_state_change

        self._state = StandbyState.DORMANT
        self._last_activity = now()
        # Re-entrant: on_wake may be called from the wake thread while tick()
        # runs on the monitor thread; both mutate state.
        self._lock = threading.RLock()

    # ---- observation -------------------------------------------------- #

    @property
    def state(self) -> StandbyState:
        with self._lock:
            return self._state

    @property
    def idle_timeout_s(self) -> float:
        return self._idle_timeout_s

    def set_idle_timeout(self, seconds: float) -> None:
        """Retune how long the brain stays warm after the last activity.

        Used by presence-adaptive standby: shorten it when the user steps away
        from the keyboard, lengthen it during an active work session. This only
        changes *when an idle brain spins down* — it never force-cuts, because
        ``on_activity`` keeps resetting the timer on every voice turn. Clamped
        to a sane floor so a bad value can't spin the brain down instantly.
        """
        with self._lock:
            self._idle_timeout_s = max(5.0, float(seconds))

    def seconds_idle(self) -> float:
        """How long since the last activity (0 while dormant is meaningless)."""
        with self._lock:
            return self._now() - self._last_activity

    # ---- events ------------------------------------------------------- #

    def on_wake(self) -> bool:
        """The wake word was heard. Spin the brain up if dormant.

        Returns True if the brain is (now) live, False if a spin-up failed.
        Idempotent while ACTIVE — a second wake just refreshes activity, it does
        not spawn a second brain.
        """
        with self._lock:
            self._last_activity = self._now()
            if self._state is StandbyState.ACTIVE:
                return True
            ok = False
            try:
                ok = bool(self._spin_up())
            except Exception:
                ok = False
            if ok:
                self._set(StandbyState.ACTIVE)
            return ok

    def on_activity(self) -> None:
        """Any conversation activity — resets the idle countdown."""
        with self._lock:
            self._last_activity = self._now()

    def tick(self) -> None:
        """Periodic housekeeping. Spins the brain down after the idle timeout.

        Deterministic: the real monitor thread calls this on an interval, and
        tests call it directly after advancing the fake clock — no sleeping.
        """
        with self._lock:
            if self._state is not StandbyState.ACTIVE:
                return
            if self._now() - self._last_activity >= self._idle_timeout_s:
                self._do_spin_down()

    def force_dormant(self) -> None:
        """Immediately spin the brain down (e.g. entering system sleep / battery
        critical). No-op if already dormant."""
        with self._lock:
            if self._state is StandbyState.ACTIVE:
                self._do_spin_down()

    # ---- internals ---------------------------------------------------- #

    def _do_spin_down(self) -> None:
        try:
            self._spin_down()
        except Exception:
            # A failing teardown must not wedge the power machine. From the
            # orchestrator's view the brain is gone; the real spin_down adapter
            # owns making process cleanup robust/idempotent (and logging).
            pass
        self._set(StandbyState.DORMANT)

    def _set(self, new: StandbyState) -> None:
        if new is self._state:
            return
        self._state = new
        if self._on_state_change is not None:
            try:
                self._on_state_change(new)
            except Exception:
                # A subscriber must never break the power state machine.
                pass
