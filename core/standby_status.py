"""Offline standby status — what `--standby-status` prints without booting.

``StandbyHealth`` reports on a *running* daemon (live brain state, breaker, the
in-progress session), which only exists inside that process. This module answers
the other question — "is standby set up, and how much has it saved over its
whole life?" — from purely static facts a fresh process can read:

  * the tuning (``StandbyConfig``),
  * the persisted lifetime duty cycle (``StandbyStatsStore``),
  * whether it will launch at login (``AutostartManager``),
  * whether the wake model is actually on disk (else standby falls back).

It is a pure assembler/formatter over already-loaded inputs, so it is unit-tested
with plain values — no settings, no registry, no filesystem.
"""

from __future__ import annotations

from typing import Optional


def offline_status(
    *,
    config=None,
    lifetime=None,
    autostart_enabled: bool = False,
    wake_model_present: bool = False,
    recent_events=None,
) -> dict:
    """Assemble the static standby status. ``lifetime`` is a ``LifetimeStats``
    (or None); it is only reported once at least one session has been banked.
    ``recent_events`` is an optional list of pre-formatted journal lines."""
    lt = None
    if lifetime is not None and getattr(lifetime, "sessions", 0) > 0:
        lt = lifetime.snapshot()
    return {
        "ready": bool(wake_model_present),   # standby proper needs the wake model
        "autostart": bool(autostart_enabled),
        "wake_model_present": bool(wake_model_present),
        "config": config.summary() if config is not None else None,
        "lifetime": lt,
        "recent": list(recent_events) if recent_events else [],
    }


def format_offline_status(status: dict, *, name: str = "AERIS") -> str:
    ready = status["ready"]
    lines = [
        f"{name} standby status — "
        + ("ready" if ready else "NOT ready (wake model missing -> falls back to --wake)"),
        f"  autostart at login: {'on' if status['autostart'] else 'off'}",
        f"  wake model:         {'present' if status['wake_model_present'] else 'MISSING'}",
    ]
    if status.get("config"):
        lines.append(f"  config:             {status['config']}")
    lt = status.get("lifetime")
    if lt:
        lines.append(
            f"  lifetime:           {lt['lifetime_dormant_pct']:.1f}% dormant across "
            f"{lt['sessions']} session(s), {lt['lifetime_wakes']} wakes")
    else:
        lines.append("  lifetime:           no history yet")
    recent = status.get("recent")
    if recent:
        lines.append("  recent activity:")
        lines.extend(f"    {ln}" for ln in recent)
    return "\n".join(lines)
