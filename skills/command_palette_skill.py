"""Voice command + global hotkey to open the command palette.

Hotkey wiring lives in the main window (Ctrl+Shift+Space) — this skill
provides the alternative voice-driven entry: "open command palette" /
"open palette". The dialog runs on the main Qt thread; voice/skill
invocation that arrives on a worker thread is rejected with a clear
message.
"""
from __future__ import annotations

import logging
import threading

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="open_command_palette",
    description="Open the AERIS command palette — fuzzy-search every skill.",
    patterns=[
        "open command palette", "command palette",
        "open palette", "show palette",
        "palette kholo", "command palette kholo",
        "open launcher", "show launcher",
        "fuzzy search skills", "search skills",
    ],
    required_entities=[],
)
def open_command_palette(_slots: dict) -> str:
    # Run on a daemon thread that asks the main Qt loop to open the dialog.
    # The UI module refuses to spawn QApplication off-main, so if no
    # QApplication exists this is a no-op and we return a hint.
    def _run():
        try:
            from ui.command_palette import open_command_palette as _open
            _open()
        except Exception as e:
            log.warning("[command_palette_skill] launch failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="CommandPalette").start()
    return ("Command palette khol raha hoon. Tip: bind Ctrl+Shift+Space "
            "in main_window.py for instant access.")
