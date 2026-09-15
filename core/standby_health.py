"""Unified standby health report — one place to see how the OS layer is doing.

Everything the standby layer knows is scattered across objects: the controller
holds the brain state, self-heal (crash) count and the spin-up breaker; the
stats hold the live duty cycle; the store holds the lifetime total; the config
holds the tuning. ``StandbyHealth`` gathers them into a single structured report
(think ``systemctl status``) and a one-line verdict — used by the tray status,
a console dump, and to decide whether to tell the user the brain is unavailable.

It reads its inputs by duck-typing and guards every optional piece, so a partial
wiring (say stats but no store) still produces a valid report, and it is
unit-tested with light fakes.
"""

from __future__ import annotations

from typing import Optional

from core.standby_breaker import BreakerState


_DEGRADED_SPEECH = "Brain is temporarily unavailable, sir. I will retry shortly."


class StandbyHealth:
    """Aggregates the standby subsystems into one health view."""

    def __init__(self, *, controller, stats=None, store=None, config=None) -> None:
        self._ctl = controller
        self._stats = stats
        self._store = store
        self._config = config

    # ---- verdict ----------------------------------------------------- #

    def _breaker(self):
        return getattr(self._ctl, "breaker", None)

    def healthy(self) -> bool:
        """Healthy unless the brain currently can't be started (breaker OPEN).

        A crash that was self-healed, or a breaker probing in HALF_OPEN, is not
        "degraded" — only a fully OPEN breaker means we can't serve a wake now.
        """
        b = self._breaker()
        if b is None:
            return True
        return b.state is not BreakerState.OPEN

    def degraded_message(self) -> Optional[str]:
        """What to say on a wake while degraded — or None when healthy."""
        return None if self.healthy() else _DEGRADED_SPEECH

    # ---- structured report ------------------------------------------- #

    def report(self) -> dict:
        state = self._ctl.state
        brain_state = getattr(state, "value", str(state))

        b = self._breaker()
        if b is not None:
            bstate = b.state
            breaker = getattr(bstate, "value", str(bstate))
            breaker_detail = b.describe()
        else:
            breaker = "n/a"
            breaker_detail = ""

        report = {
            "healthy": self.healthy(),
            "brain": {
                "state": brain_state,
                "crashes": int(getattr(self._ctl, "crashes", 0)),
                "breaker": breaker,
                "breaker_detail": breaker_detail,
            },
            "session": self._stats.snapshot() if self._stats is not None else None,
            "lifetime": self._lifetime(),
            "config": self._config.summary() if self._config is not None else None,
        }
        return report

    def _lifetime(self) -> Optional[dict]:
        if self._store is None:
            return None
        try:
            if self._stats is not None:
                # persisted baseline + the still-running current session
                return self._store.merged(self._stats.snapshot()).snapshot()
            return self._store.baseline.snapshot()
        except Exception:
            return None

    # ---- human-readable ---------------------------------------------- #

    def spoken_summary(self) -> str:
        """A natural-language health line for TTS (answers 'system status?')."""
        r = self.report()
        b = r["brain"]
        parts = ["I'm healthy" if r["healthy"] else "I'm degraded"]
        parts.append(f"the brain is {b['state']}")
        if r["session"]:
            parts.append(f"dormant {r['session']['dormant_pct']:.0f} percent of the time")
        if b["crashes"]:
            n = b["crashes"]
            parts.append(f"I self-healed {n} time" + ("s" if n != 1 else ""))
        return ", ".join(parts) + ", sir."

    def report_line(self) -> str:
        r = self.report()
        b = r["brain"]
        parts = [f"AERIS {'OK' if r['healthy'] else 'DEGRADED'}",
                 f"brain {b['state']}"]
        if b["crashes"]:
            parts.append(f"{b['crashes']} recovered")
        if b["breaker"] not in ("closed", "n/a"):
            parts.append(f"breaker {b['breaker']}")
        if r["session"]:
            parts.append(f"{r['session']['dormant_pct']:.0f}% dormant")
        return " · ".join(parts)

    def format_report(self) -> str:
        """Multi-line dump for a console / tray tooltip."""
        r = self.report()
        b = r["brain"]
        lines = [
            f"AERIS standby — {'OK' if r['healthy'] else 'DEGRADED'}",
            f"  brain:    {b['state']}"
            + (f"  ({b['breaker_detail']})" if not r["healthy"] else ""),
            f"  breaker:  {b['breaker']}   self-heals: {b['crashes']}",
        ]
        if r["session"]:
            s = r["session"]
            lines.append(f"  session:  {s['dormant_pct']:.0f}% dormant of "
                         f"{s['uptime_s']:.0f}s · {s['spinups']} spin-ups · "
                         f"{s['wakes']} wakes")
        if r["lifetime"]:
            lt = r["lifetime"]
            lines.append(f"  lifetime: {lt['lifetime_dormant_pct']:.1f}% dormant "
                         f"across {lt['sessions']} session(s)")
        if r["config"]:
            lines.append(f"  config:   {r['config']}")
        return "\n".join(lines)
