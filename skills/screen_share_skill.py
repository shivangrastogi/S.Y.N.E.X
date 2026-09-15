"""Phase 4 — LIVE bidirectional screen share over the bridge.

  * laptop_screen_share — "laptop screen dikhao"  → the laptop streams its
                          OWN screen to the phone's live view.
  * screen_share_stop   — "screen share band karo" → stops BOTH directions
                          (laptop→phone stream + phone→laptop stream) and
                          closes the laptop live window.

The phone side has its own Exit button that also stops whichever share is
active; these skills are the laptop-voice/typing equivalent.

Frames relay through Firestore (~1 frame/1.3s, hard-compressed) so it stays
on the free tier — "live refresh", not 30fps video. A 5-minute safety cap
auto-stops a forgotten share.
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
    name="laptop_screen_share",
    description="Stream this laptop's screen live to the paired phone.",
    patterns=[
        "laptop screen dikhao", "laptop ki screen dikhao",
        "share laptop screen", "laptop screen phone pe dikhao",
        "laptop screen mirror karo", "laptop screen phone pe bhejo",
        "mera laptop screen phone pe dikhao", "show laptop screen on phone",
    ],
    required_entities=[],
)
def laptop_screen_share(_slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    from core.cloud_bridge import get_bridge
    b = get_bridge()
    # Phase 5: WebRTC first (remote-desktop grade — smooth, works anywhere).
    if b.start_webrtc_stream():
        return ("Laptop screen ab phone pe live 📺 (WebRTC — smooth). "
                "Phone app khula rakho. Rokne ke liye 'screen share band karo'.")
    # Fallback: old H.264/JPEG-over-socket path.
    if b.start_laptop_stream():
        return ("Laptop screen phone pe live 📺 (fallback mode). "
                "Rokne ke liye 'screen share band karo'.")
    return "Laptop screen stream shuru nahi ho paaya."


@skill(
    name="screen_share_stop",
    description="Stop any live screen share (both directions).",
    patterns=[
        "screen share band karo", "stop screen share", "screen sharing stop",
        "screen share stop karo", "screen band karo", "stop sharing screen",
        "live screen band karo", "screen mirror band karo",
    ],
    required_entities=[],
)
def screen_share_stop(_slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi."
    from core.cloud_bridge import get_bridge
    b = get_bridge()
    b.stop_webrtc_stream()      # WebRTC laptop → phone
    b.stop_laptop_stream()      # legacy laptop → phone
    b.stop_phone_stream()       # phone → laptop
    # Ask the GUI to close its live window too, if open.
    try:
        if b._on_control:
            b._on_control("stop_phone_stream")
    except Exception:
        pass
    return "Screen share band 🛑 — dono taraf ki live sharing ruk gayi."
