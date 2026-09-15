"""Eternal Live Presence — the always-on "soul" of A.E.R.I.S.

Where ``core/presence.py`` only answers *"is a face in front of the camera?"*,
this module is the layer above it: a single, always-running heartbeat that
**fuses every ambient signal the assistant already collects** — camera
presence, idle/power state, the foreground-app workspace profile, and the
wall-clock time-of-day — into one coherent ``PresenceContext`` and a small
state machine (AWAY → IDLE → ACTIVE → FOCUS).

On top of that fused context it generates *proactive moments*: short,
human, Hinglish-flavoured nudges that make the assistant feel present and
useful rather than a passive command box — e.g. a "welcome back" on return
from idle, a hydration/stretch nudge after a long focus stretch, a
time-of-day greeting, a gentle low-battery heads-up, a quiet farewell when
you walk away.

The whole point is that it stays *usable* — not annoying. Every moment kind
has its own cooldown, the engine honours quiet hours and the global privacy
switch, and it degrades gracefully when any one signal source is missing
(no camera ⇒ idle + workspace + clock still drive everything).

Nothing here touches Qt or TTS directly. Consumers register a listener and
decide how to surface a moment (speak it, pulse the orb, toast it):

    eng = get_eternal_presence()
    eng.add_listener(lambda m: print(m.state, m.kind, m.text))
    eng.start()
    ...
    eng.stop()
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

log = logging.getLogger(__name__)


# ── Presence states ──────────────────────────────────────────────────── #

STATE_AWAY = "away"        # no one here (camera says absent, or long idle)
STATE_IDLE = "idle"        # here, but not actively interacting
STATE_ACTIVE = "active"    # at the machine, doing things
STATE_FOCUS = "focus"      # sustained deep-work in a CODING/MEETING profile

_ALL_STATES = (STATE_AWAY, STATE_IDLE, STATE_ACTIVE, STATE_FOCUS)


# ── Tunables (overridable via settings → "presence" block) ───────────── #

_HEARTBEAT_S = 8.0             # fuse-and-decide cadence
_FOCUS_ENTER_S = 8 * 60        # sustained active work before we call it FOCUS
_FOCUS_NUDGE_EVERY_S = 50 * 60 # break/hydration nudge cadence inside FOCUS
_RETURN_WELCOME_GAP_S = 6 * 60 # min away/idle gap before a "welcome back"
_QUIET_START_H = 23           # 23:00 .. 07:00 → no spoken proactive moments
_QUIET_END_H = 7

# Per-kind cooldowns so nothing repeats into nagging.
_COOLDOWNS_S = {
    "greeting": 6 * 3600,       # time-of-day greeting: a few times a day max
    "welcome_back": 5 * 60,
    "farewell": 5 * 60,
    "focus_nudge": _FOCUS_NUDGE_EVERY_S,
    "battery_low": 20 * 60,
    "workspace": 4 * 60,
}


# ── Time of day ──────────────────────────────────────────────────────── #

def _time_of_day(now: Optional[datetime] = None) -> str:
    h = (now or datetime.now()).hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 21:
        return "evening"
    return "night"


def _is_quiet(now: Optional[datetime] = None,
              start_h: int = _QUIET_START_H, end_h: int = _QUIET_END_H) -> bool:
    h = (now or datetime.now()).hour
    if start_h <= end_h:
        return start_h <= h < end_h
    return h >= start_h or h < end_h          # wraps past midnight


# ── Data carriers ────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class PresenceContext:
    """A single fused snapshot of "what's going on right now"."""
    state: str
    present: bool                 # camera sees a person (False if no camera)
    is_idle: bool
    on_battery: bool
    battery_pct: int
    profile: str                  # workspace profile, e.g. CODING / MEETING
    time_of_day: str
    active_for_s: float           # how long continuously ACTIVE/FOCUS
    away_for_s: float             # how long continuously AWAY/IDLE
    ts: float = field(default_factory=time.monotonic)


@dataclass(frozen=True)
class PresenceMoment:
    """A proactive thing the assistant wants to surface."""
    kind: str                     # greeting | welcome_back | farewell | ...
    text: str                     # human, ready-to-speak line
    state: str                    # presence state when it fired
    priority: int = 1             # 0 ambient · 1 normal · 2 important
    ts: float = field(default_factory=time.time)


# ── Engine ───────────────────────────────────────────────────────────── #

class EternalPresence:
    """Always-on ambient-presence orchestrator. Process-wide singleton via
    ``get_eternal_presence()``; tests may instantiate freely and inject a
    fake clock / heartbeat."""

    def __init__(self, *, heartbeat_s: float = _HEARTBEAT_S,
                 name: str = "A.E.R.I.S",
                 clock: Callable[[], datetime] = datetime.now):
        self._heartbeat = max(1.0, heartbeat_s)
        self._name = name
        self._clock = clock
        self._enabled = True                 # master switch (settings-driven)
        self._quiet_start = _QUIET_START_H
        self._quiet_end = _QUIET_END_H

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._listeners: List[Callable[[PresenceMoment], None]] = []
        self._state_listeners: List[Callable[[str, str], None]] = []

        self._state = STATE_AWAY
        self._state_since = time.monotonic()
        self._ctx: Optional[PresenceContext] = None
        self._last_moment_at: dict[str, float] = {}
        self._greeted_tod: Optional[str] = None      # last greeted time-of-day
        self._last_focus_nudge_at = 0.0

        # Cached signal — updated by the camera-presence listener (push) and
        # by the heartbeat reading the pull-based monitors.
        self._cam_present: Optional[bool] = None     # None ⇒ no camera signal

    # ── lifecycle ────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return True
            self._load_settings()
            if not self._enabled:
                log.info("[eternal] disabled via settings; not starting.")
                return False
            self._wire_sources()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="EternalPresence", daemon=True)
            self._thread.start()
            log.info("[eternal] live presence started (heartbeat=%.1fs).",
                     self._heartbeat)
            return True

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        log.info("[eternal] live presence stopped.")

    # ── public surface ───────────────────────────────────────────────

    def add_listener(self, fn: Callable[[PresenceMoment], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def add_state_listener(self, fn: Callable[[str, str], None]) -> None:
        """Register ``fn(new_state, prev_state)``, fired on every state
        transition (away/idle/active/focus). Distinct from moment listeners —
        used by consumers that gate behaviour on presence (e.g. the gesture
        gate) rather than reacting to proactive nudges."""
        with self._lock:
            self._state_listeners.append(fn)

    def state(self) -> str:
        return self._state

    def context(self) -> Optional[PresenceContext]:
        return self._ctx

    # ── source wiring (all best-effort / optional) ───────────────────

    def _wire_sources(self) -> None:
        # Camera presence (push). Absent camera ⇒ stays None ⇒ ignored.
        try:
            from core.presence import get_presence_engine
            eng = get_presence_engine()
            if eng.start():
                eng.add_listener(self._on_camera_event)
                self._cam_present = eng.is_present()
        except Exception as e:
            log.debug("[eternal] camera presence unavailable: %s", e)

        # Power/idle + workspace monitors are pull-based via snapshot();
        # just make sure they're running.
        for mod in ("core.power_state", "core.workspace_profile"):
            try:
                __import__(mod)
                getattr(__import__(mod, fromlist=["get_monitor"]),
                        "get_monitor")().start()
            except Exception as e:
                log.debug("[eternal] %s monitor unavailable: %s", mod, e)

    def _on_camera_event(self, event: str) -> None:
        self._cam_present = (event == "present")

    # ── the heartbeat ────────────────────────────────────────────────

    def _run(self) -> None:
        if self._stop.wait(1.5):              # let boot settle
            return
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("[eternal] heartbeat tick raised")
            if self._stop.wait(self._heartbeat):
                return

    def _tick(self) -> None:
        ctx = self._fuse()
        with self._lock:
            self._ctx = ctx
        for moment in self._decide(ctx):
            self._emit(moment)

    def _fuse(self) -> PresenceContext:
        """Read every source, derive the next state, build the context."""
        is_idle, on_batt, pct = False, False, 100
        try:
            from core.power_state import get_monitor as _pm
            snap = _pm().snapshot()
            is_idle, on_batt, pct = snap.is_idle, snap.on_battery, snap.percent
        except Exception:
            pass

        profile = "IDLE"
        try:
            from core.workspace_profile import get_monitor as _wm
            profile = _wm().snapshot().profile
        except Exception:
            pass

        now_dt = self._clock()
        present = self._cam_present

        # Derive the next state. Camera (when available) is authoritative for
        # AWAY; otherwise long idle stands in for "away".
        if present is False:
            new_state = STATE_AWAY
        elif is_idle and present is not True:
            new_state = STATE_AWAY if present is None else STATE_IDLE
        elif is_idle:
            new_state = STATE_IDLE
        else:
            new_state = STATE_ACTIVE

        prev = self._state
        if new_state != prev:
            held = time.monotonic() - self._state_since
            self._state = new_state
            self._state_since = time.monotonic()
            self._journal_state(new_state, prev, held, profile)
            self._fan_out_state(new_state, prev)

        active_for = (time.monotonic() - self._state_since
                      if self._state in (STATE_ACTIVE, STATE_FOCUS) else 0.0)
        away_for = (time.monotonic() - self._state_since
                    if self._state in (STATE_AWAY, STATE_IDLE) else 0.0)

        # Promote sustained ACTIVE in a work profile to FOCUS.
        if (self._state == STATE_ACTIVE
                and active_for >= _FOCUS_ENTER_S
                and profile in ("CODING", "MEETING")):
            self._state = STATE_FOCUS
            self._journal_state(STATE_FOCUS, STATE_ACTIVE, active_for, profile)
            self._fan_out_state(STATE_FOCUS, STATE_ACTIVE)
            # keep _state_since so active_for keeps climbing

        return PresenceContext(
            state=self._state, present=bool(present), is_idle=is_idle,
            on_battery=on_batt, battery_pct=pct, profile=profile,
            time_of_day=_time_of_day(now_dt), active_for_s=active_for,
            away_for_s=away_for,
        )

    # ── moment decisions ─────────────────────────────────────────────

    def _decide(self, ctx: PresenceContext) -> List[PresenceMoment]:
        """Pure-ish: turn a context + cooldowns into zero or more moments."""
        out: List[PresenceMoment] = []
        if self._suppressed():
            return out
        prev = getattr(self, "_prev_state_for_decide", STATE_AWAY)
        self._prev_state_for_decide = ctx.state

        # 1. Return to the machine → welcome back / greeting.
        came_back = prev in (STATE_AWAY, STATE_IDLE) and ctx.state in (
            STATE_ACTIVE, STATE_FOCUS)
        if came_back:
            tod = ctx.time_of_day
            if self._greeted_tod != tod and self._cool("greeting"):
                self._greeted_tod = tod
                out.append(self._moment(
                    "greeting", self._greeting_line(tod), ctx, priority=1))
            elif self._cool("welcome_back"):
                out.append(self._moment(
                    "welcome_back", self._welcome_back_line(ctx), ctx))

        # 2. Walked away → quiet farewell (low priority, non-spoken by default).
        left = prev in (STATE_ACTIVE, STATE_FOCUS) and ctx.state == STATE_AWAY
        if left and self._cool("farewell"):
            out.append(self._moment(
                "farewell", self._farewell_line(ctx), ctx, priority=0))

        # 3. Long focus stretch → break / hydration nudge.
        if ctx.state == STATE_FOCUS and ctx.active_for_s >= _FOCUS_ENTER_S:
            if (time.monotonic() - self._last_focus_nudge_at
                    >= _FOCUS_NUDGE_EVERY_S and self._cool("focus_nudge")):
                self._last_focus_nudge_at = time.monotonic()
                out.append(self._moment(
                    "focus_nudge", self._focus_nudge_line(ctx), ctx))

        # 4. On battery and low → gentle heads-up (only while present).
        if (ctx.state in (STATE_ACTIVE, STATE_FOCUS)
                and ctx.on_battery and ctx.battery_pct <= 20
                and self._cool("battery_low")):
            out.append(self._moment(
                "battery_low",
                f"Heads up — battery {ctx.battery_pct}% pe hai, charger laga lo.",
                ctx, priority=2))

        return out

    # ── line templates (Hinglish, swappable) ─────────────────────────

    def _greeting_line(self, tod: str) -> str:
        n = self._name
        return {
            "morning":   f"Good morning! {n} ready hai — aaj ka plan bata do.",
            "afternoon": f"Good afternoon. {n} yahin hai, kuch chahiye?",
            "evening":   f"Good evening! Din kaisa raha? {n} present hai.",
            "night":     f"Late night session? {n} saath hai — bolo.",
        }.get(tod, f"{n} ready hai.")

    def _welcome_back_line(self, ctx: PresenceContext) -> str:
        return "Welcome back — wahin se continue karein?"

    def _farewell_line(self, ctx: PresenceContext) -> str:
        return "Theek hai, main yahin hoon. Aate hi bata dena."

    def _focus_nudge_line(self, ctx: PresenceContext) -> str:
        mins = int(ctx.active_for_s // 60)
        return (f"{mins} min se focus mode chal raha hai — ek choti si "
                f"stretch + paani break le lo, phir wapas.")

    # ── plumbing ──────────────────────────────────────────────────────

    def _moment(self, kind: str, text: str, ctx: PresenceContext,
                priority: int = 1) -> PresenceMoment:
        self._last_moment_at[kind] = time.monotonic()
        return PresenceMoment(kind=kind, text=text, state=ctx.state,
                              priority=priority)

    def _cool(self, kind: str) -> bool:
        # Never fired → cooldown is definitionally elapsed. (Must NOT default to
        # 0.0 and compare against monotonic(): on a freshly-booted machine
        # monotonic() can be < the cooldown, e.g. the 6 h "greeting" window, which
        # would wrongly suppress the first-ever greeting → "welcome back" on cold
        # start instead of "good morning".)
        if kind not in self._last_moment_at:
            return True
        return (time.monotonic() - self._last_moment_at[kind]) >= _COOLDOWNS_S.get(kind, 60)

    def _suppressed(self) -> bool:
        # Privacy switch wins outright; quiet hours suppress everything too.
        try:
            from core.privacy_mode import is_on
            if is_on():
                return True
        except Exception:
            pass
        return _is_quiet(self._clock(), self._quiet_start, self._quiet_end)

    def _fan_out_state(self, new_state: str, prev: str) -> None:
        with self._lock:
            subs = list(self._state_listeners)
        for fn in subs:
            try:
                fn(new_state, prev)
            except Exception:
                log.debug("[eternal] state listener raised", exc_info=True)

    def _journal_state(self, state: str, prev: str, held_s: float,
                       profile: str) -> None:
        try:
            from core.presence_journal import get_journal
            get_journal().record_state(state, prev=prev, held_s=held_s,
                                       profile=profile)
        except Exception:
            log.debug("[eternal] journal state failed", exc_info=True)

    def _emit(self, moment: PresenceMoment) -> None:
        try:
            from core.log_setup import event
            event("presence_moment", kind=moment.kind, state=moment.state,
                  priority=moment.priority)
        except Exception:
            pass
        try:
            from core.presence_journal import get_journal
            get_journal().record_moment(moment.kind, moment.text,
                                        priority=moment.priority,
                                        state=moment.state)
        except Exception:
            log.debug("[eternal] journal moment failed", exc_info=True)
        with self._lock:
            subs = list(self._listeners)
        for fn in subs:
            try:
                fn(moment)
            except Exception:
                log.debug("[eternal] listener raised", exc_info=True)

    def _load_settings(self) -> None:
        try:
            import json
            import os
            path = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "data", "settings.json")
            with open(path, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
        except Exception:
            return
        self._name = cfg.get("assistant_name", self._name)
        p = cfg.get("presence", {}) if isinstance(cfg.get("presence"), dict) else {}
        self._enabled = bool(p.get("enabled", True))
        if "heartbeat_s" in p:
            try:
                self._heartbeat = max(1.0, float(p["heartbeat_s"]))
            except (TypeError, ValueError):
                pass
        try:
            self._quiet_start = int(p.get("quiet_start_h", self._quiet_start))
            self._quiet_end = int(p.get("quiet_end_h", self._quiet_end))
        except (TypeError, ValueError):
            pass


# ── singleton + install helper ───────────────────────────────────────── #

_DEFAULT: Optional[EternalPresence] = None
_DEFAULT_LOCK = threading.Lock()


def get_eternal_presence() -> EternalPresence:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = EternalPresence()
        return _DEFAULT


def install(speak: Optional[Callable[[str], None]] = None,
            on_moment: Optional[Callable[[PresenceMoment], None]] = None
            ) -> EternalPresence:
    """Convenience wiring used by the GUI / engine boot.

    ``speak`` (if given) is called with the moment text for priority >= 1
    moments; ``on_moment`` always receives the full moment so the GUI can
    also pulse the orb / toast it. Registers a graceful-shutdown hook.
    """
    eng = get_eternal_presence()

    def _listener(m: PresenceMoment) -> None:
        if on_moment is not None:
            try:
                on_moment(m)
            except Exception:
                log.debug("[eternal] on_moment raised", exc_info=True)
        if speak is not None and m.priority >= 1:
            try:
                speak(m.text)
            except Exception:
                log.debug("[eternal] speak raised", exc_info=True)

    eng.add_listener(_listener)
    eng.start()
    try:
        from core.shutdown import register
        register("eternal_presence", lambda: eng.stop())
    except Exception:
        pass
    return eng


if __name__ == "__main__":      # pragma: no cover — manual smoke
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    e = EternalPresence(heartbeat_s=2.0)
    e.add_listener(lambda m: print(f"  > [{m.state}] {m.kind}: {m.text}"))
    e.start()
    try:
        time.sleep(30)
    finally:
        e.stop()
