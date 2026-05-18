"""Voice control for the AERIS Automation Engine.

Skills exposed:
  * ``routine_list``     — "list routines", "show automation"
  * ``routine_run``      — "run morning workspace", "start coding mode"
  * ``routine_enable``   — "enable battery saver"
  * ``routine_disable``  — "disable coding mode"
  * ``routine_status``   — "is morning routine on"

All these dispatch through ``core.automation.get_engine()``; the engine
is started by ``main_window`` at boot, so the skill just consults it.
"""
from __future__ import annotations

import logging
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _engine():
    """Lazy import so the skill registry doesn't pull automation in at
    discover time (it's started later by main_window).
    """
    from core.automation import get_engine
    return get_engine()


def _find(query: str):
    q = (query or "").strip()
    if not q:
        return None
    return _engine().find_by_name(q)


@skill(
    name="routine_list",
    description="List all automation routines and their current state",
    patterns=[
        "list routines", "show routines", "automation list",
        "kya routines hain", "routines dikhao", "automation kya hai",
        "show automations", "automation status",
    ],
)
def routine_list(_slots: dict) -> str:
    routines = _engine().list_routines()
    if not routines:
        return "Koi routines configured nahi hain. data/routines.json check karo."
    lines = []
    for r in routines:
        state = "ON " if r.enabled else "off"
        last = ""
        if r.fire_count:
            from datetime import datetime as _dt
            last = f" · last fired {_dt.fromtimestamp(r.last_fired_ts).strftime('%b %d %H:%M')}"
        lines.append(f"  [{state}] {r.name}  ·  {r.trigger.summary()}  ·  {len(r.actions)} actions{last}")
    return f"{len(routines)} routines:\n" + "\n".join(lines)


@skill(
    name="routine_run",
    description="Run a routine right now by name (bypasses its trigger)",
    patterns=[
        "run morning routine", "start coding mode", "trigger battery saver",
        "run nightly summary", "execute routine", "kick off routine",
        "routine chalao", "abhi chalao", "trigger karo",
    ],
    required_entities=["content"],
    prompts={"content": "Kaunsi routine chalani hai?"},
)
def routine_run(slots: dict) -> str:
    q = (slots.get("content") or "").strip()
    if not q:
        return "Routine ka naam batao."
    r = _find(q)
    if r is None:
        return f"'{q}' naam ki routine nahi mili. 'list routines' bolo."
    if _engine().run_routine(r.id, reason="voice"):
        return f"'{r.name}' chala diya — {len(r.actions)} steps."
    return f"Routine '{r.id}' run nahi ho saki."


@skill(
    name="routine_enable",
    description="Enable a routine so its trigger fires it",
    patterns=[
        "enable morning routine", "enable coding mode", "enable battery saver",
        "routine on karo", "enable automation",
    ],
    required_entities=["content"],
    prompts={"content": "Kaunsi routine enable karni hai?"},
)
def routine_enable(slots: dict) -> str:
    q = (slots.get("content") or "").strip()
    if not q:
        return "Routine ka naam batao."
    r = _find(q)
    if r is None:
        return f"'{q}' nahi mili."
    if _engine().set_enabled(r.id, True):
        return f"'{r.name}' enabled — {r.trigger.summary()}."
    return "Enable fail ho gaya."


@skill(
    name="routine_disable",
    description="Disable a routine so its trigger no longer fires",
    patterns=[
        "disable morning routine", "disable coding mode", "disable battery saver",
        "routine off karo", "disable automation", "stop routine",
    ],
    required_entities=["content"],
    prompts={"content": "Kaunsi routine disable karni hai?"},
)
def routine_disable(slots: dict) -> str:
    q = (slots.get("content") or "").strip()
    if not q:
        return "Routine ka naam batao."
    r = _find(q)
    if r is None:
        return f"'{q}' nahi mili."
    if _engine().set_enabled(r.id, False):
        return f"'{r.name}' disabled."
    return "Disable fail ho gaya."


@skill(
    name="routine_status",
    description="Show the current state of a specific routine",
    patterns=[
        "routine status", "is coding mode on", "morning routine status",
        "routine kya status hai", "battery saver chalu hai kya",
    ],
    required_entities=["content"],
    prompts={"content": "Kaunsi routine ka status chahiye?"},
)
def routine_status(slots: dict) -> str:
    q = (slots.get("content") or "").strip()
    if not q:
        return "Routine ka naam batao."
    r = _find(q)
    if r is None:
        return f"'{q}' nahi mili."
    state = "ON" if r.enabled else "off"
    last = ""
    if r.fire_count:
        from datetime import datetime as _dt
        last = f", last fired {_dt.fromtimestamp(r.last_fired_ts).strftime('%b %d at %H:%M')} ({r.fire_count} times total)"
    return (f"'{r.name}' is {state}. Trigger: {r.trigger.summary()}. "
            f"{len(r.actions)} actions{last}.")


@skill(
    name="routine_reload",
    description="Re-read data/routines.json from disk (after editing it manually)",
    patterns=[
        "reload routines", "refresh routines", "routines refresh karo",
        "reload automation", "routines reload",
    ],
)
def routine_reload(_slots: dict) -> str:
    n = _engine().reload()
    return f"{n} routines reload ho gaye."
