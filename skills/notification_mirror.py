"""Voice control for the Windows notification mirror.

Skills:
  * ``notification_mirror_on``  — subscribe + speak new toasts aloud
  * ``notification_mirror_off`` — stop
  * ``last_notification``       — describe the most recent toast
  * ``notification_mirror_status``
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="notification_mirror_on",
    description="Read each new Windows toast notification aloud via TTS.",
    patterns=[
        "read my notifications", "notification mirror on",
        "speak notifications", "notifications bolo",
        "mirror notifications", "narrate toasts",
        "notifications ko padho",
    ],
    required_entities=[],
)
def notification_mirror_on(_slots: dict) -> str:
    try:
        from core.notify_listener import get_listener, install_speaker_hook
    except Exception as e:
        return f"notify_listener load fail: {e}"
    install_speaker_hook()
    ok, msg = get_listener().start()
    return msg


@skill(
    name="notification_mirror_off",
    description="Stop reading Windows toasts aloud.",
    patterns=[
        "stop reading notifications", "notification mirror off",
        "stop notifications", "notifications band karo",
        "stop narrating toasts",
    ],
    required_entities=[],
)
def notification_mirror_off(_slots: dict) -> str:
    try:
        from core.notify_listener import get_listener
    except Exception as e:
        return f"notify_listener load fail: {e}"
    get_listener().stop()
    return "Notification mirror OFF."


@skill(
    name="last_notification",
    description="Describe the most recent Windows toast notification.",
    patterns=[
        "last notification", "what was the last notification",
        "pichli notification", "recent toast",
        "last toast batao", "kya notification aya tha",
    ],
    required_entities=[],
)
def last_notification(_slots: dict) -> str:
    try:
        from core.notify_listener import get_listener
    except Exception as e:
        return f"notify_listener load fail: {e}"
    eng = get_listener()
    n = eng.last_notification()
    if not n:
        if not eng.is_available():
            return ("Notification mirror unavailable — install with "
                    "'pip install winsdk' for Windows toast access.")
        return "Abhi tak koi notification nahi aaya (ya mirror OFF hai)."
    when = time.strftime("%H:%M", time.localtime(n.get("ts") or time.time()))
    app = n.get("app") or "?"
    title = n.get("title") or "(no title)"
    body = (n.get("body") or "").strip()
    body_part = f" — {body}" if body else ""
    return f"[{when}] {app}: {title}{body_part}"


@skill(
    name="notification_mirror_status",
    description="Report whether notification mirror is on / available.",
    patterns=[
        "notification mirror status", "is notification mirror on",
        "notifications status", "notification status",
    ],
    required_entities=[],
)
def notification_mirror_status(_slots: dict) -> str:
    try:
        from core.notify_listener import get_listener
    except Exception as e:
        return f"notify_listener load fail: {e}"
    eng = get_listener()
    avail = "available" if eng.is_available() else "UNAVAILABLE (install winsdk)"
    state = "ON" if eng.is_running() else "OFF"
    return f"Notification mirror: {state} · backend: {avail}."
