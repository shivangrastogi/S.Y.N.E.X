"""Telemetry dashboard voice surface + text-only digest."""
from __future__ import annotations

import logging
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="open_telemetry_dashboard",
    description="Open the AERIS telemetry dashboard — usage stats for "
                "gestures, skills, workspace, memory.",
    patterns=[
        "open telemetry", "open telemetry dashboard",
        "telemetry dashboard", "show stats panel",
        "open stats panel", "open dashboard",
        "telemetry kholo", "dashboard kholo",
    ],
    required_entities=[],
)
def open_telemetry_dashboard(_slots: dict) -> str:
    def _run():
        try:
            from ui.telemetry_dashboard import open_telemetry_dashboard as _open
            _open()
        except Exception as e:
            log.warning("[telemetry_skill] launch failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="TelemetryDashboard").start()
    return "Telemetry dashboard khol raha hoon."


@skill(
    name="telemetry_digest",
    description="Print a text digest of usage stats (gestures, skills, "
                "memos, journal, KG, faces) over the last hour.",
    patterns=[
        "telemetry digest", "usage digest", "stats digest",
        "telemetry summary", "show telemetry",
        "stats summary",
    ],
    required_entities=[],
)
def telemetry_digest(_slots: dict) -> str:
    try:
        from core.telemetry import snapshot
    except Exception as e:
        return f"telemetry load fail: {e}"
    snap = snapshot(window_h=1.0)
    g = snap["gesture"]; s = snap["skill"]
    lines = [
        "AERIS telemetry digest (last 1 h):",
        f"  Gestures: {g['fired']} fired · {g['blocked']} blocked · {g['total']} total",
        f"  Top skills: " + ", ".join(f"{n}={c}" for n, c in s["ranked"][:5])
                       if s["ranked"] else "  Top skills: (none)",
        f"  Memos: {snap['memos']} · journal: {snap['journal']} · "
        f"KG triples: {snap['kg']} · faces: {snap['faces']}",
    ]
    return "\n".join(lines)
