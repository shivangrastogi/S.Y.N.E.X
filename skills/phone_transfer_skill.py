"""Laptop → phone transfers (Phase 2B): screenshot + clipboard.

  * screenshot_to_phone — capture the screen and send the image straight
                          to the phone (see it on your phone from your desk).
  * clipboard_to_phone  — push the laptop clipboard text to the phone.
  * send_image_to_phone — send a named image from ~/Pictures to the phone.

Images go base64 (downscaled JPEG) over the same E2E-encrypted bridge —
no Firebase Storage / extra setup.
"""
from __future__ import annotations

import logging
import os

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _paired() -> bool:
    try:
        from core.cloud_bridge import get_bridge
        return bool(get_bridge().status().get("paired"))
    except Exception:
        return False


@skill(
    name="screenshot_to_phone",
    description="Capture the laptop screen and send the image to the phone.",
    patterns=[
        "screenshot phone pe bhejo", "send screenshot to phone",
        "screenshot phone par bhejo", "phone pe screenshot bhejo",
        "screen phone pe bhejo", "laptop screenshot phone pe",
    ],
    required_entities=[],
)
def screenshot_to_phone(_slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    try:
        from skills.screenshot_skill import _capture_full, _next_filename
        path = _next_filename("to_phone")
        if not _capture_full(path):
            return "Screenshot capture nahi hua."
    except Exception as e:
        return f"Screenshot fail: {e}"
    from core.cloud_bridge import get_bridge
    ok, msg = get_bridge().send_image_to_phone(path, caption="Laptop screenshot")
    return "Screenshot phone pe bhej diya 📱" if ok else f"Bhejne mein dikkat: {msg}"


@skill(
    name="clipboard_to_phone",
    description="Send the laptop clipboard text to the phone.",
    patterns=[
        "clipboard phone pe bhejo", "send clipboard to phone",
        "copied text phone pe bhejo", "phone pe clipboard bhejo",
        "yeh phone pe bhejo",
    ],
    required_entities=[],
)
def clipboard_to_phone(_slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    try:
        import pyperclip
        text = (pyperclip.paste() or "").strip()
    except Exception as e:
        return f"Clipboard padha nahi ja saka: {e}"
    if not text:
        return "Clipboard khali hai — pehle kuch copy karo."
    from core.cloud_bridge import get_bridge
    ok = get_bridge().send_to_phone({
        "id": os.urandom(4).hex(), "type": "clipboard",
        "text": text[:4000], "reply_to": None, "extra": {},
    })
    return "Clipboard phone pe bhej diya 📋" if ok else "Bhejne mein dikkat."


@skill(
    name="image_to_phone",
    description="Send a named image (from ~/Pictures) to the phone.",
    patterns=[
        "yeh image phone pe bhejo", "send image to phone",
        "photo phone pe bhejo", "picture phone par bhejo",
    ],
    required_entities=[],
)
def image_to_phone(slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    raw = (slots.get("raw_text") or "").lower()
    # crude name grab: last word(s) after 'image'/'photo'
    name = ""
    for kw in ("image", "photo", "picture"):
        if kw in raw:
            name = raw.split(kw, 1)[0].strip()
            break
    pics = os.path.join(os.path.expanduser("~"), "Pictures")
    found = None
    try:
        for root, _dirs, files in os.walk(pics):
            for fn in files:
                if fn.lower().endswith((".png", ".jpg", ".jpeg")) and \
                        (not name or name in fn.lower()):
                    found = os.path.join(root, fn)
                    break
            if found:
                break
    except Exception:
        pass
    if not found:
        return "Us naam ki image ~/Pictures mein nahi mili."
    from core.cloud_bridge import get_bridge
    ok, msg = get_bridge().send_image_to_phone(found, caption=os.path.basename(found))
    return f"'{os.path.basename(found)}' phone pe bhej diya 📱" if ok else f"Dikkat: {msg}"
