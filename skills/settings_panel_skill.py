"""Voice command to open the settings panel.

The actual dialog lives in ``ui/settings_panel.py`` — this skill just
launches it. Runs in a daemon thread so the brain loop isn't blocked
while the dialog is up.
"""
from __future__ import annotations

import logging
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="open_settings_panel",
    description="Open the AERIS settings dialog — edit voice, gestures, "
                "masters, browser without touching settings.json.",
    patterns=[
        "open settings panel", "open settings", "settings panel kholo",
        "show settings", "settings kholo", "edit settings",
        "preferences panel", "open preferences", "preferences kholo",
        "configure aeris", "aeris settings", "tweak settings",
    ],
    required_entities=[],
)
def open_settings_panel(_slots: dict) -> str:
    def _run():
        try:
            from ui.settings_panel import open_settings_panel as _open
            ok = _open()
            log.info("[settings_panel_skill] dialog closed (saved=%s)", ok)
        except Exception as e:
            log.warning("[settings_panel_skill] launch failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="SettingsPanel").start()
    return "Settings panel khol raha hoon — save kar ke close karo."
