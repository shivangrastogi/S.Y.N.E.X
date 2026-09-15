"""Open the permissions matrix editor."""
from __future__ import annotations

import logging
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="open_permissions_editor",
    description="Open the masters × gestures permissions matrix — edit "
                "every per-user gesture allowance in one grid.",
    patterns=[
        "open permissions editor", "permissions editor",
        "edit permissions", "permissions panel",
        "open master permissions", "master permissions panel",
        "permissions matrix", "open permissions matrix",
        "permissions kholo",
    ],
    required_entities=[],
)
def open_permissions_editor(_slots: dict) -> str:
    def _run():
        try:
            from ui.permissions_editor import open_permissions_editor as _open
            _open()
        except Exception as e:
            log.warning("[permissions_editor_skill] launch failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="PermissionsEditor").start()
    return "Permissions editor khol raha hoon — save kar ke close karo."
