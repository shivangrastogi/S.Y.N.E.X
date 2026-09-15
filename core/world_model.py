"""World Model — a live snapshot of "what's true right now" (Q2·M4).

The planner and the Initiative Engine both need one cheap, structured view of
the current situation instead of each re-deriving it. This aggregates the
signals AERIS already has — the clock, open/blocked goals, the autonomy state,
quiet hours. Calendar / email / location get folded in later (they need the
Gmail + Calendar integrations); this is the honest, dependency-free core.

Also exposes ``situation_initiatives()`` — a source the Initiative Engine can
plug into so a goal that is *blocked needing your input* actually surfaces.

Pure + injectable (goal store, gate, clock) → unit-tests with fakes.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


def _part_of_day(h: int) -> str:
    if h < 5:
        return "raat"
    if h < 12:
        return "subah"
    if h < 17:
        return "dopahar"
    if h < 20:
        return "shaam"
    return "raat"


_WEEKDAYS = ["Somwar", "Mangalwar", "Budhwar", "Guruwar", "Shukrawar",
             "Shaniwar", "Ravivar"]


# A continuous focus stretch past this earns a gentle "take a break" nudge.
_FOCUS_BREAK_MIN = 90
# Battery at/below this while unplugged is worth flagging.
_BATTERY_LOW = 20


@dataclass
class Situation:
    ts: float
    part_of_day: str            # subah | dopahar | shaam | raat
    weekday: str
    open_goals: int = 0
    awaiting_user: list = field(default_factory=list)  # [{id, text, ask}]
    due_goals: list = field(default_factory=list)      # [{id, text}] need_time now due
    awake: bool = True          # False when panic-halted
    quiet_hours: bool = False
    battery: Optional[dict] = None      # {percent, on_battery, plugged}
    focus_min: int = 0                  # current *continuous* focus minutes

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


class WorldModel:
    def __init__(self, *,
                 goals_provider: Optional[Callable[[], Any]] = None,
                 gate_provider: Optional[Callable[[], Any]] = None,
                 power_provider: Optional[Callable[[], Any]] = None,
                 presence_provider: Optional[Callable[[], Any]] = None,
                 now_fn: Callable[[], float] = time.time):
        self._goals = goals_provider or _default_goals
        self._gate = gate_provider or _default_gate
        self._power = power_provider or _default_power
        self._presence = presence_provider or _default_presence
        self._now = now_fn

    def situation(self) -> Situation:
        t = self._now()
        dt = datetime.fromtimestamp(t)
        st = Situation(ts=t, part_of_day=_part_of_day(dt.hour),
                       weekday=_WEEKDAYS[dt.weekday()])
        store = _safe(self._goals)
        if store is not None:
            try:
                openg = store.open_goals()
                st.open_goals = len(openg)
                st.awaiting_user = [
                    {"id": g.id, "text": g.text, "ask": getattr(g, "ask", None)}
                    for g in openg
                    if g.state == "blocked"
                    and getattr(g, "blocker", None) == "need_user"]
                st.due_goals = [{"id": g.id, "text": g.text}
                                for g in store.due(t)]
            except Exception as e:
                log.debug("[world] goals read failed: %s", e)
        gate = _safe(self._gate)
        if gate is not None:
            try:
                st.awake = not gate._is_panic()
                st.quiet_hours = gate._in_quiet(t)
            except Exception:
                pass
        mon = _safe(self._power)
        if mon is not None:
            try:
                snap = mon.snapshot()
                st.battery = {"percent": int(snap.percent),
                              "on_battery": bool(snap.on_battery),
                              "plugged": bool(snap.plugged)}
            except Exception:
                pass
        st.focus_min = _continuous_focus_min(_safe(self._presence), t)
        return st


def _continuous_focus_min(journal, now: float) -> int:
    """Minutes the user has been *continuously* in FOCUS — i.e. how long ago the
    most recent state transition into 'focus' was, or 0 if not focusing now."""
    if journal is None:
        return 0
    try:
        recs = journal.state_records()
        if not recs:
            return 0
        last = recs[-1]
        if last.get("state") != "focus":
            return 0
        started = datetime.fromisoformat(last["ts"]).timestamp()
        return max(0, int((now - started) // 60))
    except Exception:
        return 0


def situation_initiatives(world: Optional[WorldModel] = None):
    """Initiative candidates from the situation the Initiative Engine can plug
    into (``extra_sources=[...]``): goals that need you or are due again, a
    battery running low, or a long unbroken focus stretch. Each carries a stable
    ``source_id`` so the engine's anti-nag/dedup only surfaces it once."""
    from core.initiative_engine import Initiative
    world = world or get_world()
    out = []
    try:
        st = world.situation()

        # A goal parked on your input. (Due need_time goals are surfaced by the
        # Initiative Engine's own built-in due source — st.due_goals is exposed
        # here as observable state, not re-emitted, to avoid a double nudge.)
        for g in st.awaiting_user:
            ask = g.get("ask") or f"'{g['text']}' ke liye aapka jawab chahiye."
            out.append(Initiative(
                text=ask, kind="goal_needs_you", action="notify_user",
                importance=0.85, timeliness=0.9, confidence=0.9, openness=0.75,
                source_id=f"await:{g['id']}", goal_id=g["id"],
                requested_level=2))

        # Battery running low on battery power.
        bat = st.battery or {}
        if bat.get("on_battery") and bat.get("percent", 100) <= _BATTERY_LOW:
            pct = bat["percent"]
            bucket = "crit" if pct <= 10 else "low"
            out.append(Initiative(
                text=f"Battery {pct}% aur charger nahi laga — kaam save kar lo.",
                kind="battery_low", action="notify_user",
                importance=0.8, timeliness=0.95, confidence=0.95, openness=0.7,
                source_id=f"battery:{bucket}", requested_level=2))

        # A long unbroken focus stretch — a gentle wellbeing nudge.
        if st.focus_min >= _FOCUS_BREAK_MIN:
            out.append(Initiative(
                text=f"{st.focus_min} min se lagataar focus mein ho — 2 min ka break?",
                kind="take_break", action="notify_user",
                importance=0.5, timeliness=0.6, confidence=0.8, openness=0.6,
                source_id="break:focus", requested_level=1))
    except Exception as e:
        log.debug("[world] situation_initiatives failed: %s", e)
    return out


def _safe(provider: Callable[[], Any]):
    try:
        return provider()
    except Exception:
        return None


def _default_goals():
    from core.goal_system import get_goal_store
    return get_goal_store()


def _default_gate():
    from core.autonomy import get_gate
    return get_gate()


def _default_power():
    from core.power_state import get_monitor
    return get_monitor()


def _default_presence():
    from core.presence_journal import get_journal
    return get_journal()


_WORLD: Optional[WorldModel] = None


def get_world() -> WorldModel:
    global _WORLD
    if _WORLD is None:
        _WORLD = WorldModel()
    return _WORLD
