"""AR overlay voice surface.

Skills:
  * ``ar_overlay_on``    — show the translucent camera-with-boxes preview
  * ``ar_overlay_off``   — hide it
  * ``ar_overlay_status``
"""
from __future__ import annotations

import logging
import re
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _corner_from(text: str) -> str:
    t = (text or "").lower()
    for c in ("top-right", "top-left", "bottom-right", "bottom-left",
              "top right", "top left", "bottom right", "bottom left"):
        if c in t:
            return c.replace(" ", "-")
    return "top-right"


@skill(
    name="ar_overlay_on",
    description="Show the AR camera overlay — translucent always-on-top "
                "live preview with YOLO bounding boxes.",
    patterns=[
        "ar overlay on", "show ar overlay",
        "ar preview on", "ar camera on",
        "show camera overlay", "translucent camera",
        "ar mode on", "augmented reality on",
    ],
    required_entities=[],
)
def ar_overlay_on(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    corner = _corner_from(text)
    def _run():
        try:
            from ui.ar_overlay import show_ar_overlay
            show_ar_overlay(corner)
        except Exception as e:
            log.warning("[ar_overlay_skill] show failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="ARShow").start()
    return f"AR overlay khol raha hoon at {corner}."


@skill(
    name="ar_overlay_off",
    description="Hide the AR camera overlay.",
    patterns=[
        "ar overlay off", "hide ar overlay",
        "ar preview off", "close ar overlay",
        "ar mode off", "augmented reality off",
    ],
    required_entities=[],
)
def ar_overlay_off(_slots: dict) -> str:
    def _run():
        try:
            from ui.ar_overlay import hide_ar_overlay
            hide_ar_overlay()
        except Exception as e:
            log.warning("[ar_overlay_skill] hide failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="ARHide").start()
    return "AR overlay OFF."


@skill(
    name="ar_overlay_status",
    description="Report whether the AR overlay is currently shown.",
    patterns=[
        "ar overlay status", "ar status",
        "is ar overlay on", "ar overlay kya hai",
    ],
    required_entities=[],
)
def ar_overlay_status(_slots: dict) -> str:
    try:
        from ui.ar_overlay import is_ar_visible
        return f"AR overlay: {'visible' if is_ar_visible() else 'hidden'}."
    except Exception as e:
        return f"ar_overlay load fail: {e}"
