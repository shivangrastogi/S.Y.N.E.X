"""Workspace tracker voice surface.

Skills:
  * ``workspace_track_on``  — start the background poller
  * ``workspace_track_off`` — stop it
  * ``workspace_summary``   — totals per app for the last hour
  * ``workspace_summary_today`` — totals for the last 24 hours
  * ``workspace_clear``     — wipe the rolling buffer
  * ``workspace_recent``    — list the last few app switches
"""
from __future__ import annotations

import logging
import time

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="workspace_track_on",
    description="Start the autonomous workspace tracker (polls foreground "
                "app every 30 s, builds a usage timeline).",
    patterns=[
        "workspace track on", "start workspace tracking",
        "track workspace", "watch my workspace",
        "workspace tracker on", "track my apps",
        "workspace track chalu karo",
    ],
    required_entities=[],
)
def workspace_track_on(_slots: dict) -> str:
    try:
        from core.workspace_tracker import get_workspace_tracker
    except Exception as e:
        return f"workspace_tracker load fail: {e}"
    t = get_workspace_tracker()
    if t.is_running():
        return "Workspace tracker already ON."
    t.start()
    return "Workspace tracker ON — polling foreground app every 30 s."


@skill(
    name="workspace_track_off",
    description="Stop the workspace tracker (keeps buffered events).",
    patterns=[
        "workspace track off", "stop workspace tracking",
        "stop watching workspace", "workspace tracker off",
        "track workspace stop", "workspace track band karo",
    ],
    required_entities=[],
)
def workspace_track_off(_slots: dict) -> str:
    try:
        from core.workspace_tracker import get_workspace_tracker
    except Exception as e:
        return f"workspace_tracker load fail: {e}"
    t = get_workspace_tracker()
    if not t.is_running():
        return "Workspace tracker was already OFF."
    t.stop()
    return "Workspace tracker OFF (events buffered)."


@skill(
    name="workspace_summary",
    description="Summarise the last hour of foreground app usage.",
    patterns=[
        "workspace summary", "what have i been doing",
        "kya kya kaam kiya is hour", "app usage summary",
        "summary of my work", "what was i working on",
        "workspace digest",
    ],
    required_entities=[],
)
def workspace_summary(_slots: dict) -> str:
    try:
        from core.workspace_tracker import get_workspace_tracker
    except Exception as e:
        return f"workspace_tracker load fail: {e}"
    return get_workspace_tracker().summary(window_s=3600.0)


@skill(
    name="workspace_summary_today",
    description="Summarise the last 24 hours of app usage.",
    patterns=[
        "workspace summary today", "aaj kya kiya",
        "today's workspace", "today app usage",
        "aaj ka workspace summary", "day workspace summary",
    ],
    required_entities=[],
)
def workspace_summary_today(_slots: dict) -> str:
    try:
        from core.workspace_tracker import get_workspace_tracker
    except Exception as e:
        return f"workspace_tracker load fail: {e}"
    return get_workspace_tracker().summary(window_s=86400.0)


@skill(
    name="workspace_clear",
    description="Wipe the workspace tracker's rolling event buffer.",
    patterns=[
        "workspace clear", "clear workspace history",
        "wipe workspace tracker", "workspace events clear",
    ],
    required_entities=[],
)
def workspace_clear(_slots: dict) -> str:
    try:
        from core.workspace_tracker import get_workspace_tracker
    except Exception as e:
        return f"workspace_tracker load fail: {e}"
    n = get_workspace_tracker().clear()
    return f"Cleared {n} workspace event(s)."


@skill(
    name="workspace_recent",
    description="Show the last 10 foreground-app switches.",
    patterns=[
        "workspace recent", "recent app switches",
        "what apps did i switch to", "last few apps",
        "workspace last switches",
    ],
    required_entities=[],
)
def workspace_recent(_slots: dict) -> str:
    try:
        from core.workspace_tracker import get_workspace_tracker, _pretty_app
    except Exception as e:
        return f"workspace_tracker load fail: {e}"
    events = get_workspace_tracker().recent_events(10)
    if not events:
        return "Koi workspace event recorded nahi hua hai."
    lines = [f"Last {len(events)} app switch(es):"]
    for e in events:
        when = time.strftime("%H:%M:%S", time.localtime(e["ts"]))
        secs = int(e["duration_s"])
        lines.append(f"  {when}  {_pretty_app(e['exe']):20s} {secs}s")
    return "\n".join(lines)
