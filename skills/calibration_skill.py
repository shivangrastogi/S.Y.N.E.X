"""Voice command to launch the gesture calibration wizard.

Runs the dialog on a daemon thread so the brain loop isn't blocked
while the user practises gestures.
"""
from __future__ import annotations

import logging
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="start_calibration_wizard",
    description="Launch the gesture calibration wizard — walks you through "
                "each gesture with live detection feedback.",
    patterns=[
        "start calibration", "calibration wizard",
        "gesture calibration", "calibrate gestures",
        "teach me gestures", "gesture tutorial",
        "start gesture tutorial", "wizard start karo",
        "gestures practice karo", "calibration kholo",
        "show me the gestures", "gesture training",
    ],
    required_entities=[],
)
def start_calibration_wizard(_slots: dict) -> str:
    def _run():
        try:
            from ui.calibration_wizard import open_calibration_wizard
            ok = open_calibration_wizard()
            log.info("[calibration_skill] wizard closed (completed=%s)", ok)
        except Exception as e:
            log.warning("[calibration_skill] launch failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="CalibrationWizard").start()
    return "Calibration wizard khol raha hoon — har gesture practice karo."
