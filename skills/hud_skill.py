"""Voice control for the heads-up overlay (HUD).

Skills:
  * ``hud_on``     — show overlay (default top-right)
  * ``hud_off``    — hide overlay
  * ``hud_move``   — move to a named corner
  * ``hud_status`` — visible / hidden
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
    name="hud_on",
    description="Show the always-on-top AERIS heads-up overlay.",
    patterns=[
        "hud on", "show hud", "heads up on", "show overlay",
        "heads up display on", "overlay on",
        "hud kholo", "hud chalu karo",
        "show heads up display",
    ],
    required_entities=[],
)
def hud_on(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    corner = _corner_from(text)
    def _run():
        try:
            from ui.hud_overlay import show_hud
            show_hud(corner)
        except Exception as e:
            log.warning("[hud_skill] show failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="HUDShow").start()
    return f"HUD ON at {corner}."


@skill(
    name="hud_off",
    description="Hide the heads-up overlay.",
    patterns=[
        "hud off", "hide hud", "heads up off",
        "hide overlay", "overlay off",
        "hud band karo", "hud hide karo",
    ],
    required_entities=[],
)
def hud_off(_slots: dict) -> str:
    def _run():
        try:
            from ui.hud_overlay import hide_hud
            hide_hud()
        except Exception as e:
            log.warning("[hud_skill] hide failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="HUDHide").start()
    return "HUD OFF."


@skill(
    name="hud_move",
    description="Move the HUD to a named corner.",
    patterns=[
        "hud move", "move hud", "hud to top right",
        "hud to top left", "hud to bottom right",
        "hud to bottom left", "hud reposition",
    ],
    required_entities=[],
)
def hud_move(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    corner = _corner_from(text)
    def _run():
        try:
            from ui.hud_overlay import hide_hud, show_hud
            hide_hud()
            show_hud(corner)
        except Exception as e:
            log.warning("[hud_skill] move failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="HUDMove").start()
    return f"HUD → {corner}."


@skill(
    name="hud_status",
    description="Report whether the HUD is currently visible.",
    patterns=[
        "hud status", "is hud on", "hud kya hai",
        "heads up status", "overlay status",
    ],
    required_entities=[],
)
def hud_status(_slots: dict) -> str:
    try:
        from ui.hud_overlay import is_hud_visible
        return f"HUD: {'visible' if is_hud_visible() else 'hidden'}."
    except Exception as e:
        return f"hud_overlay load fail: {e}"
