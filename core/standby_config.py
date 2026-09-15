"""Standby preferences, loaded from ``core.settings`` and validated.

The always-on behaviour should be tunable and persistent, not hardcoded in the
entry point — how long to keep the brain warm, whether to keep listening on
battery, when a battery counts as "critical", how often to tick.

``StandbyConfig.from_settings(get)`` reads ``standby.*`` keys via any getter with
the ``get(key, default)`` shape (real: ``core.settings.get``; tests: a dict).
Every value is clamped to a sane range and falls back to its default on a bad
type, so a corrupt or hand-edited setting can never wedge standby.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


def _num(get: Callable, key: str, default: float, lo: float, hi: float) -> float:
    try:
        v = float(get(key, default))
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(lo, min(hi, v))


def _flag(get: Callable, key: str, default: bool) -> bool:
    v = get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return default


@dataclass(frozen=True)
class StandbyConfig:
    idle_timeout_s: float = 180.0        # warm brain time (user present)
    away_idle_timeout_s: float = 30.0    # warm brain time (user idle/away)
    critical_battery_pct: int = 15       # at/below this on battery → dormant
    keep_awake_on_battery: bool = True   # keep listening while on battery
    tick_interval_s: float = 5.0         # idle-check / exec-reassert cadence
    ask_timeout_s: float = 12.0          # per-turn brain request timeout
    checkpoint_interval_s: float = 300.0  # bank lifetime duty cycle this often
    breaker_threshold: int = 3           # consecutive spin-up fails → trip breaker
    breaker_cooldown_s: float = 10.0     # base backoff after the breaker trips
    quiet_start: str = ""                # 'HH:MM' — quiet-hours start ('' = off)
    quiet_end: str = ""                  # 'HH:MM' — quiet-hours end

    @classmethod
    def from_settings(cls, get: Callable) -> "StandbyConfig":
        idle = _num(get, "standby.idle_timeout_s", 180.0, 10.0, 3600.0)
        # The away warm-time is meaningless if longer than the active one, so
        # clamp its ceiling to the active timeout (floor stays a sane 5s).
        away = _num(get, "standby.away_idle_timeout_s", 30.0, 5.0, idle)
        return cls(
            idle_timeout_s=idle,
            away_idle_timeout_s=away,
            critical_battery_pct=int(
                _num(get, "standby.critical_battery_pct", 15, 1, 99)),
            keep_awake_on_battery=_flag(
                get, "standby.keep_awake_on_battery", True),
            tick_interval_s=_num(get, "standby.tick_interval_s", 5.0, 1.0, 60.0),
            ask_timeout_s=_num(get, "standby.ask_timeout_s", 12.0, 2.0, 120.0),
            checkpoint_interval_s=_num(
                get, "standby.checkpoint_interval_s", 300.0, 30.0, 3600.0),
            breaker_threshold=int(
                _num(get, "standby.breaker_threshold", 3, 1, 20)),
            breaker_cooldown_s=_num(
                get, "standby.breaker_cooldown_s", 10.0, 1.0, 600.0),
            quiet_start=str(get("standby.quiet_start", "") or ""),
            quiet_end=str(get("standby.quiet_end", "") or ""),
        )

    def summary(self) -> str:
        batt = ("listen on battery" if self.keep_awake_on_battery
                else "sleep on battery")
        return (f"idle {self.idle_timeout_s:.0f}s (away {self.away_idle_timeout_s:.0f}s) "
                f"· critical {self.critical_battery_pct}% "
                f"· {batt} · tick {self.tick_interval_s:.0f}s")
