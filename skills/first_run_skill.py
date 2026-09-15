"""First-run wizard launcher."""
from __future__ import annotations

import logging
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="open_first_run_wizard",
    description="Open the AERIS first-run setup wizard — guides through "
                "face enrollment + voice + theme + diagnostics.",
    patterns=[
        "first run wizard", "open first run wizard",
        "setup wizard", "open setup wizard",
        "onboarding wizard", "aeris setup",
        "first run setup", "welcome wizard",
        "setup aeris",
    ],
    required_entities=[],
)
def open_first_run_wizard(_slots: dict) -> str:
    def _run():
        try:
            from ui.first_run_wizard import open_first_run_wizard as _open
            _open()
        except Exception as e:
            log.warning("[first_run_skill] launch failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="FirstRunWizard").start()
    return "First-run setup wizard khol raha hoon."
