"""Standby stack assembly — the single place the standby OS is wired together.

The many standby modules (orchestrator, breaker, reflex, stats, journal, health,
power policy, quiet hours, daemon) have to be composed *just so*: the controller
gets the breaker + reflex + a state-change callback that feeds both stats and the
journal; the daemon gets the checkpoint + wake observer + degraded speech + quiet
hours; the control hook bridges controller → daemon/health. That composition used
to live inline in ``main.py --standby`` and was only AST-checked.

``build_standby_stack`` extracts it so the *wiring itself* is unit-testable:
``main.py`` calls it with the real IO components (Vosk, STT/TTS, brain proxy,
power monitor); the integration tests call it with fakes and drive whole
sessions through the real, wired objects. Clocks are injected (a monotonic
``now`` for the state machine/stats, a wall ``now_dt`` for reflex/quiet-hours),
so a full day can be simulated deterministically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from core.standby_runtime import StandbyController
from core.standby_breaker import SpinUpBreaker
from core.standby_reflex import ReflexRouter
from core.standby_daemon import StandbyDaemon
from core.standby_power import StandbyPowerPolicy
from core.standby_quiet import QuietHours
from core.standby_stats import StandbyStats
from core.standby_persist import StandbyStatsStore, LifetimeStats
from core.standby_journal import StandbyJournal
from core.standby_health import StandbyHealth
from core.standby_controls import StandbyControls


@dataclass
class StandbyStack:
    """The fully-wired standby subsystem."""
    daemon: StandbyDaemon
    controls: StandbyControls
    health: StandbyHealth
    controller: StandbyController
    stats: StandbyStats
    journal: StandbyJournal
    store: StandbyStatsStore
    lifetime: LifetimeStats


def build_standby_stack(
    *,
    brain,
    stt: Callable[[], Optional[str]],
    wake_detector,
    cfg,
    stats_path: str,
    journal_path: str,
    tts: Optional[Callable[[str], None]] = None,
    power_monitor=None,
    now: Callable[[], float] = time.monotonic,
    now_dt: Callable[[], datetime] = datetime.now,
    log: Optional[Callable[[str], None]] = None,
) -> StandbyStack:
    """Compose the whole standby subsystem from its parts. See module docstring."""
    _log = log or (lambda *_: None)

    stats = StandbyStats(now=now)
    store = StandbyStatsStore(stats_path)
    lifetime = store.load()

    journal = StandbyJournal(path=journal_path)
    journal.load()
    journal.record("boot")

    controller = StandbyController(
        brain=brain,
        idle_timeout_s=cfg.idle_timeout_s,
        away_idle_timeout_s=cfg.away_idle_timeout_s,
        critical_battery_pct=cfg.critical_battery_pct,
        now=now,
        # State changes feed telemetry AND the journal (and an optional log line).
        on_state_change=lambda s: (stats.on_state_change(s),
                                   journal.on_state_change(s),
                                   _log(f"  [standby] brain -> {s.value}")),
        breaker=SpinUpBreaker(threshold=cfg.breaker_threshold,
                              base_cooldown_s=cfg.breaker_cooldown_s, now=now),
        on_event=journal.record,        # crash / breaker_open / breaker_close
        reflex=ReflexRouter(now=now_dt),
    )

    health = StandbyHealth(controller=controller, stats=stats,
                           store=store, config=cfg)

    daemon = StandbyDaemon(
        controller=controller,
        wake_detector=wake_detector,
        power_monitor=power_monitor,
        stt=stt,
        tts=tts,
        tick_interval_s=cfg.tick_interval_s,
        power_policy=StandbyPowerPolicy(
            keep_awake_on_battery=cfg.keep_awake_on_battery,
            critical_pct=cfg.critical_battery_pct),
        checkpoint=lambda: (store.commit(stats.snapshot()), journal.flush()),
        checkpoint_interval_s=cfg.checkpoint_interval_s,
        wake_observer=lambda: (stats.on_wake(), journal.record("wake")),
        degraded_check=health.degraded_message,
        quiet_hours=QuietHours.parse(cfg.quiet_start, cfg.quiet_end),
        now_dt=now_dt,
    )

    # Control actions the controller can't do itself (own daemon/health).
    def _on_control(action: str) -> Optional[str]:
        if action == "pause":
            daemon.pause_listening()
            journal.record("control", "pause")
            return "Paused. Resume me from the tray, sir."
        if action == "status":
            return health.spoken_summary()
        return None
    controller.set_on_control(_on_control)

    controls = StandbyControls(daemon, stats=stats, health=health)

    return StandbyStack(daemon=daemon, controls=controls, health=health,
                        controller=controller, stats=stats, journal=journal,
                        store=store, lifetime=lifetime)
