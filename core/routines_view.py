"""Read-only introspection over ``data/routines.json``.

The automation engine *runs* routines; this module just *describes* them so the
user can ask "what's scheduled?" / "what fires at 9am?" without opening the JSON.
Reuses ``Trigger.summary()`` / ``Action.summary()`` from ``core.automation`` so
the prose matches what the engine itself reports.

Pure read + format — no scheduler, no threads — so it's unit-testable against a
fixture file.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "routines.json")


def load_routines(path: Optional[str] = None) -> list:
    """Return ``Routine`` objects from the JSON file (empty list on any error)."""
    p = path or _DEFAULT_PATH
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
        from core.automation import Routine
        return [Routine.from_dict(r) for r in data.get("routines", [])]
    except (OSError, ValueError) as e:
        log.debug("[routines_view] load failed: %s", e)
        return []


def cron_hour(cron: str) -> Optional[int]:
    """The hour field of a 5-field cron, or None if not a fixed numeric hour."""
    parts = (cron or "").strip().split()
    if len(parts) != 5:
        return None
    hr = parts[1]
    return int(hr) if hr.isdigit() else None


def routines_at(hour: int, path: Optional[str] = None) -> list:
    """Time-triggered routines whose cron hour equals ``hour`` (0–23)."""
    out = []
    for r in load_routines(path):
        if r.trigger.kind == "time":
            if cron_hour(r.trigger.params.get("cron", "")) == hour:
                out.append(r)
    return out


def _line(r) -> str:
    state = "on" if r.enabled else "off"
    return f"• {r.name} — {r.trigger.summary()} [{state}, {len(r.actions)} steps]"


def summarize_routines(path: Optional[str] = None, *, enabled_only: bool = False) -> str:
    """A human list of all routines (or only the enabled ones)."""
    routines = load_routines(path)
    if enabled_only:
        routines = [r for r in routines if r.enabled]
    if not routines:
        scope = "enabled " if enabled_only else ""
        return f"Koi {scope}routine set nahi hai abhi, sir."
    n_on = sum(1 for r in routines if r.enabled)
    head = f"{len(routines)} routine(s), {n_on} enabled:"
    return head + "\n" + "\n".join(_line(r) for r in routines)


def summarize_at(hour: int, path: Optional[str] = None) -> str:
    """Describe what fires at a given hour."""
    hits = routines_at(hour, path)
    label = f"{hour:02d}:00"
    if not hits:
        return f"{label} pe kuch schedule nahi hai, sir."
    return f"{label} pe: " + "; ".join(
        f"{r.name} ({'on' if r.enabled else 'off'})" for r in hits
    )
