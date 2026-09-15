"""Proactive source: offer to activate a Mode at the right time of day.

Plugs into initiative_engine as an ``extra_source``. Returns L2 OFFERs like
"Raat ho rahi hai — sleep mode chalu karu?". The engine's salience routing,
quiet-hours, cooldown and anti-nag memory decide whether it actually surfaces
— this source only proposes; restraint stays with the engine.

Wind-down (sleep) fires 21:00–22:59, i.e. BEFORE typical quiet hours (23:00),
so it has a chance to surface; a 3am nudge would (rightly) be dropped anyway.
"""
from __future__ import annotations

import datetime as _dt
import time
from typing import Callable, Optional

from core.initiative_engine import Initiative

# (mode_key, hour_lo, hour_hi_inclusive, weekdays_only, text, importance, timeliness)
_RULES = [
    ("sleep", 21, 22, False,
     "Raat ho rahi hai — sleep mode chalu karu? (brightness low + mute)",
     0.50, 0.85),
    ("work", 9, 10, True,
     "Kaam ka time ho gaya — work mode on karu? (focus + DND)",
     0.50, 0.80),
]


def _default_engine():
    from core.mode_engine import get_mode_engine
    return get_mode_engine()


def make_source(now_fn: Callable[[], float] = time.time,
                engine_getter: Optional[Callable] = None):
    """Build a zero-arg source callable for the initiative engine."""
    getter = engine_getter or _default_engine

    def source() -> list:
        try:
            eng = getter()
        except Exception:
            return []
        if eng is None:
            return []
        modes = eng.list_modes()
        active = set(eng.active())
        dt = _dt.datetime.fromtimestamp(now_fn())
        hour, weekday = dt.hour, dt.weekday()
        out: list = []
        for key, lo, hi, weekdays_only, text, imp, tim in _RULES:
            if key not in modes or key in active:
                continue
            if not (lo <= hour <= hi):
                continue
            if weekdays_only and weekday >= 5:      # Sat/Sun
                continue
            out.append(Initiative(
                text=text, kind="mode_suggest", action="notify_user",
                importance=imp, timeliness=tim, confidence=0.7, openness=0.6,
                source_id=f"mode_suggest:{key}", requested_level=2))
        return out

    return source


# default source used by the live engine wiring
mode_suggestion_source = make_source()
