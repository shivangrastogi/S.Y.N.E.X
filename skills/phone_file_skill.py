"""Send a file from the laptop to the paired phone (Phase 6).

"phone pe file bhejo" → the GUI pops a file picker; the chosen file is
chunked and streamed to the phone over the encrypted relay (works from
anywhere, any size). The phone reassembles + saves it.

Incoming files (phone → laptop) land in the laptop's Downloads folder;
the GUI shows a chat note when one arrives (wired in main_window).
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _paired() -> bool:
    try:
        from core.cloud_bridge import get_bridge
        return bool(get_bridge().status().get("paired"))
    except Exception:
        return False


@skill(
    name="phone_send_file",
    description="Send a file from this laptop to the paired phone (opens a "
                "file picker).",
    patterns=[
        "phone pe file bhejo", "file phone pe bhejo", "send file to phone",
        "phone ko file bhejo", "mobile pe file bhejo", "send a file to phone",
        "laptop se phone pe file bhejo",
    ],
    required_entities=[],
)
def phone_send_file(_slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    # Sentinel — the GUI catches this, opens a QFileDialog on the GUI thread,
    # and calls cloud_bridge.send_file_to_phone with the chosen path.
    return "[pick_file_phone]"
