"""Copy an image to the Windows clipboard so it can be pasted into chat / docs.

Two paths:
  * ``last_screenshot_to_clipboard`` — most-recent file under ~/Pictures/AERIS
  * ``image_to_clipboard`` — fuzzy-find an image under ~/Pictures and copy it

Implementation: open the image with Pillow, encode as DIB (BMP minus the
14-byte file header), push via Win32 SetClipboardData(CF_DIB).
"""
from __future__ import annotations

import ctypes
import io
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"

# Win32 clipboard format constants
_CF_DIB = 8
_GMEM_MOVEABLE = 0x0002


def _aeris_pics_dir() -> Path:
    return Path.home() / "Pictures" / "AERIS"


def _newest_screenshot() -> Optional[Path]:
    d = _aeris_pics_dir()
    if not d.is_dir():
        return None
    candidates = [p for p in d.iterdir()
                  if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _resolve_image(query: str) -> Optional[Path]:
    """Treat query as an absolute path; else fuzzy under ~/Pictures."""
    if not query:
        return None
    p = Path(os.path.expanduser(os.path.expandvars(query)))
    if p.is_file():
        return p
    root = Path.home() / "Pictures"
    if not root.is_dir():
        return None
    q = query.lower()
    candidates: list[Path] = []
    for r, _dirs, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")) and q in fn.lower():
                candidates.append(Path(r) / fn)
        if len(candidates) >= 100:
            break
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _strip_verb(text: str) -> str:
    if not text:
        return ""
    return re.sub(
        r"^(?:please\s+)?"
        r"(?:copy|put|send|share|upload)\s+"
        r"(?:image|picture|screenshot|photo|file)?\s*"
        r"(?:to|in|into)?\s*(?:clipboard|to\s+clipboard)?\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip(" \"',.?")


def _push_dib_to_clipboard(img_path: Path) -> tuple[bool, str]:
    """Push the image at ``img_path`` to the Windows clipboard as CF_DIB."""
    if not _IS_WIN:
        return False, "Clipboard image copy sirf Windows pe chalti hai."
    try:
        from PIL import Image  # type: ignore
    except Exception as e:
        return False, f"Pillow nahi mila: {e}. pip install Pillow."

    try:
        with Image.open(img_path) as im:
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="BMP")
        data = buf.getvalue()
        # Strip the 14-byte BMP file header — CF_DIB starts at BITMAPINFOHEADER.
        if len(data) < 14:
            return False, "BMP data unexpectedly short."
        dib = data[14:]

        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32

        if not u32.OpenClipboard(0):
            return False, "OpenClipboard fail."
        try:
            u32.EmptyClipboard()
            hglobal = k32.GlobalAlloc(_GMEM_MOVEABLE, len(dib))
            if not hglobal:
                return False, "GlobalAlloc fail."
            ptr = k32.GlobalLock(hglobal)
            if not ptr:
                k32.GlobalFree(hglobal)
                return False, "GlobalLock fail."
            ctypes.memmove(ptr, dib, len(dib))
            k32.GlobalUnlock(hglobal)
            if not u32.SetClipboardData(_CF_DIB, hglobal):
                k32.GlobalFree(hglobal)
                return False, "SetClipboardData fail."
            # On success, ownership transferred to the clipboard — don't free.
            return True, f"Copied {img_path.name} to clipboard."
        finally:
            u32.CloseClipboard()
    except Exception as e:
        return False, f"Clipboard copy fail: {e}"


# ── last_screenshot_to_clipboard ───────────────────────────────────


@skill(
    name="last_screenshot_to_clipboard",
    description="Copy the most-recent AERIS screenshot to clipboard as image.",
    patterns=[
        "copy last screenshot", "last screenshot to clipboard",
        "last screenshot copy karo", "share last screenshot",
        "send last screenshot", "screenshot ko clipboard mein copy karo",
        "copy recent screenshot", "share latest screenshot",
    ],
    required_entities=[],
)
def last_screenshot_to_clipboard(_slots: dict) -> str:
    p = _newest_screenshot()
    if p is None:
        return ("Pictures/AERIS mein koi screenshot nahi mila. "
                "'screenshot lo' bolo to ek le lo pehle.")
    ok, msg = _push_dib_to_clipboard(p)
    if ok:
        return msg + " Ab Ctrl+V se paste karo."
    return msg


# ── image_to_clipboard ─────────────────────────────────────────────


@skill(
    name="image_to_clipboard",
    description="Copy an image (path or fuzzy name from ~/Pictures) to clipboard.",
    patterns=[
        "copy image to clipboard", "put image in clipboard",
        "share image", "upload image",
        "image clipboard me copy karo",
        "send image", "send picture",
        "copy picture to clipboard",
    ],
    required_entities=[],
)
def image_to_clipboard(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_verb(text)
    if not query:
        return "Kaunsi image? Path do ya naam: 'copy image ocean.jpg to clipboard'."
    p = _resolve_image(query)
    if p is None:
        return f"'{query}' jaisi koi image nahi mili."
    ok, msg = _push_dib_to_clipboard(p)
    return msg + (" Ab Ctrl+V se paste karo." if ok else "")
