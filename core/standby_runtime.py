"""Standby runtime — wires the tiered-wake StandbyOrchestrator to the *real*
Brain service, wake word and power monitor.

``core.standby_orchestrator`` is the pure power state machine (DORMANT ⇄
ACTIVE). This module is the adapter layer that gives it real hands:

  * ``BrainLifecycle`` — turns a ``core.service_bus.ServiceProxy`` for the Brain
    into the orchestrator's ``spin_up() -> bool`` / ``spin_down()`` contract, and
    dispatches a turn (``ask``) to the live brain.
  * ``StandbyController`` — composes the orchestrator + a BrainLifecycle into the
    daemon's decision core: on a wake it spins the brain up, transcribes,
    dispatches, and refreshes activity; a periodic ``tick`` spins the brain back
    down after idle; a battery-critical power change forces dormancy.

Everything is injection-based (the proxy, the clock, the STT function) so the
whole decision flow is unit-tested with fakes — no process spawn, no model
load, no threads. The thin thread/loop that actually drives ``tick`` and the
wake detector lives in the ``--standby`` entry point (next step) and is the only
part that needs the real services.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from core.standby_orchestrator import StandbyOrchestrator, StandbyState
from core.standby_breaker import SpinUpBreaker, BreakerState


class BrainLifecycle:
    """Adapts a Brain ``ServiceProxy`` to the orchestrator's spin_up/spin_down.

    Failures are swallowed into safe returns: a spin_up that raises reads as
    "brain did not come up" (orchestrator stays dormant), and ``ask`` errors
    (not running / timeout / bad reply) read as "no answer".
    """

    def __init__(self, proxy, *, ask_timeout: float = 12.0) -> None:
        self._proxy = proxy
        self._ask_timeout = ask_timeout

    def spin_up(self) -> bool:
        try:
            return bool(self._proxy.start())
        except Exception:
            return False

    def spin_down(self) -> None:
        try:
            if self._proxy.is_alive():
                self._proxy.stop()
        except Exception:
            pass

    def is_up(self) -> bool:
        try:
            return bool(self._proxy.is_alive())
        except Exception:
            return False

    def ask(self, text: str) -> Optional[str]:
        """Dispatch one utterance to the live brain; return its reply or None."""
        try:
            msg = self._proxy.request(
                "utterance", {"text": text}, timeout=self._ask_timeout
            )
            payload = getattr(msg, "payload", None) or {}
            reply = payload.get("reply")
            return reply or None
        except Exception:
            return None


class StandbyController:
    """The daemon's decision core: wake → spin up → answer → idle → spin down.

    Parameters
    ----------
    brain:
        A ``BrainLifecycle`` (or anything with ``spin_up``/``spin_down``/``ask``).
    idle_timeout_s:
        Quiet seconds in ACTIVE before the brain is torn down. This is the
        *active* warm-time — used while the user is present at the keyboard.
    away_idle_timeout_s:
        Optional shorter warm-time used once the user goes idle (steps away from
        the keyboard). None disables presence adaptation (warm-time stays fixed).
    critical_battery_pct:
        On battery at/below this percent, force the brain dormant to save power.
    now, on_state_change:
        Passed through to the orchestrator (injectable clock, state callback).
    """

    def __init__(
        self,
        *,
        brain: BrainLifecycle,
        idle_timeout_s: float = 180.0,
        away_idle_timeout_s: Optional[float] = None,
        critical_battery_pct: int = 15,
        now: Callable[[], float] = time.monotonic,
        on_state_change: Optional[Callable[[StandbyState], None]] = None,
        breaker: Optional[SpinUpBreaker] = None,
        on_event: Optional[Callable[[str, str], None]] = None,
        reflex=None,
        on_control: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        self._brain = brain
        self._critical_pct = int(critical_battery_pct)
        self._on_event = on_event  # optional journal hook (kind, detail)
        self._reflex = reflex      # optional Tier-0 ReflexRouter (.match(text))
        # Host hook for control actions the controller can't do itself
        # (pause listening, speak status, …). Set at build time or via setter.
        self._on_control = on_control
        # Presence-adaptive warm-times: the base (active) timeout, and the
        # shorter one applied when the user is idle. away=None → no adaptation.
        self._base_idle_timeout_s = float(idle_timeout_s)
        self._away_idle_timeout_s = (
            float(away_idle_timeout_s) if away_idle_timeout_s is not None else None
        )
        # Circuit breaker so a brain that won't start isn't hammered every wake.
        self._breaker = breaker or SpinUpBreaker(now=now)
        self._orch = StandbyOrchestrator(
            spin_up=self._guarded_spin_up,   # breaker-gated
            spin_down=brain.spin_down,
            idle_timeout_s=idle_timeout_s,
            now=now,
            on_state_change=on_state_change,
        )
        self._crashes = 0  # brain processes reconciled after an unexpected death

    def _emit(self, kind: str, detail: str = "") -> None:
        if self._on_event is not None:
            try:
                self._on_event(kind, detail)
            except Exception:
                pass

    def _guarded_spin_up(self) -> bool:
        """Spin-up gated by the circuit breaker. When the breaker is OPEN this
        returns False *without* attempting an expensive spawn (fail fast); a
        real attempt records success/failure so the breaker can trip/recover.
        Breaker transitions are emitted to the journal."""
        if not self._breaker.allow():
            return False
        before = self._breaker.state
        ok = self._brain.spin_up()
        if ok:
            self._breaker.record_success()
        else:
            self._breaker.record_failure()
        after = self._breaker.state
        if after is BreakerState.OPEN and before is not BreakerState.OPEN:
            self._emit("breaker_open", self._breaker.describe())
        elif after is BreakerState.CLOSED and before is not BreakerState.CLOSED:
            self._emit("breaker_close", "brain recovered")
        return ok

    @property
    def state(self) -> StandbyState:
        return self._orch.state

    @property
    def crashes(self) -> int:
        """How many times an ACTIVE brain was found dead and reconciled."""
        return self._crashes

    @property
    def breaker_state(self) -> BreakerState:
        """Current spin-up circuit-breaker state (for status / health)."""
        return self._breaker.state

    @property
    def breaker(self) -> SpinUpBreaker:
        return self._breaker

    def _brain_alive(self) -> bool:
        """Best-effort liveness of the brain process. If we can't tell, assume
        alive so we never thrash a healthy brain."""
        probe = getattr(self._brain, "is_up", None)
        if probe is None:
            return True
        try:
            return bool(probe())
        except Exception:
            return False

    def _reconcile_liveness(self) -> bool:
        """Self-healing: if we believe the brain is ACTIVE but its process has
        actually died (crash / OOM / killed), drop the state machine back to
        DORMANT so the very next spin-up respawns a fresh brain instead of
        dispatching turns into a corpse. Returns True if a death was reconciled.
        """
        if self._orch.state is StandbyState.ACTIVE and not self._brain_alive():
            self._crashes += 1
            self._emit("crash", f"brain died (#{self._crashes})")
            self._orch.force_dormant()   # emits on_state_change → banks the time
            return True
        return False

    def handle_wake(self, stt: Callable[[], Optional[str]]) -> Optional[str]:
        """The wake word fired. Transcribe first; answer Tier-0 reflexes with the
        brain still dormant; otherwise spin the brain up, dispatch, and return.

        Returns None if there was no speech, the brain could not come up, or it
        gave no answer. Transcribing *before* spin-up means a false wake (no
        words) or a trivial reflex ("what time is it") never pays the ~2GB spawn.
        """
        # Heal first: if a previously-ACTIVE brain died, drop to DORMANT so a
        # spin-up below cleanly respawns instead of dispatching into a corpse.
        self._reconcile_liveness()

        text: Optional[str]
        try:
            text = stt()
        except Exception:
            text = None

        if not text:
            # False wake / no words — do NOT spawn the brain for nothing.
            if self._orch.state is StandbyState.ACTIVE:
                self._orch.on_activity()
            return None

        # Tier-0 fast-path: control commands and trivial queries, both handled
        # with no brain dispatch (control may change the power state directly).
        if self._reflex is not None:
            control = self._reflex_control(text)
            if control is not None:
                reply = self._run_control(control)
                if reply is not None:
                    return reply

            reflex_reply = self._reflex.match(text)
            if reflex_reply is not None:
                self._emit("reflex", text[:40])
                if self._orch.state is StandbyState.ACTIVE:
                    self._orch.on_activity()   # keep an already-warm brain warm
                return reflex_reply

        if not self._orch.on_wake():
            return None  # brain refused to come up → stay dormant

        reply = self._brain.ask(text)
        self._orch.on_activity()
        return reply

    def _reflex_control(self, text: str) -> Optional[str]:
        """Ask the reflex router for a control-action name (safe if the router
        predates control support)."""
        fn = getattr(self._reflex, "control", None)
        if fn is None:
            return None
        try:
            return fn(text)
        except Exception:
            return None

    def _run_control(self, action: str) -> Optional[str]:
        """Execute a Tier-0 control command and return the spoken confirmation.
        Returns None for an unknown action (falls through to normal handling)."""
        if action == "sleep":
            self._emit("control", "sleep")
            self._orch.force_dormant()          # drop the brain now (no-op if dormant)
            return "Going to sleep, sir."
        if action == "wake":
            self._emit("control", "wake")
            ok = self._orch.on_wake()           # pre-warm the brain (breaker-gated)
            return "I'm awake, sir." if ok else "I couldn't wake up just now, sir."
        # App/daemon-level actions (pause listening, status, …) belong to the
        # host, which owns those subsystems — delegate.
        if self._on_control is not None:
            self._emit("control", action)
            try:
                return self._on_control(action)
            except Exception:
                return None
        return None

    def set_on_control(self, fn: Optional[Callable[[str], Optional[str]]]) -> None:
        """Wire (or replace) the host control hook after construction."""
        self._on_control = fn

    def tick(self) -> None:
        """Periodic housekeeping — reconcile a dead brain, then spin the brain
        down after the idle timeout."""
        self._reconcile_liveness()
        self._orch.tick()

    def on_power_change(self, on_battery: bool, percent: int, plugged: bool) -> None:
        """Battery-critical while unplugged → drop the heavy brain now."""
        if on_battery and int(percent) <= self._critical_pct:
            self._orch.force_dormant()

    def force_dormant(self) -> None:
        self._orch.force_dormant()

    def set_idle_timeout(self, seconds: float) -> None:
        """Retune the brain's warm-time (presence-adaptive standby)."""
        self._orch.set_idle_timeout(seconds)

    def on_user_idle(self, is_idle: bool) -> None:
        """Presence signal from the OS input-idle monitor.

        When the user steps away from the keyboard (``is_idle`` True) shorten the
        brain's warm-time so it spins down soon after the current conversation
        ends; when they return, restore the full active warm-time so follow-ups
        during a work session don't re-pay the spin-up. No-op unless an
        ``away_idle_timeout_s`` was configured.

        Safe by construction: this only moves *when an already-idle brain spins
        down*. A live voice conversation keeps calling ``on_activity``, so even
        the short away-timeout never cuts someone off mid-sentence.
        """
        if self._away_idle_timeout_s is None:
            return
        target = self._away_idle_timeout_s if is_idle else self._base_idle_timeout_s
        self._orch.set_idle_timeout(target)
