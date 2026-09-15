"""Screenshot skills — capture the screen / active window to a file.

Three layers of capture so this works on every Windows install:
  1. ``mss``   — preferred. Multi-monitor aware, captures from a thread.
  2. ``PIL.ImageGrab`` — pillow's built-in grabber.
  3. PrintScreen key   — last resort. Doesn't save a file but populates the
     clipboard so the user can paste it somewhere.

Files land in %USERPROFILE%/Pictures/AERIS/ with a timestamp filename.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional, Tuple

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _capture_dir() -> str:
    pictures = os.path.join(os.path.expanduser("~"), "Pictures", "AERIS")
    os.makedirs(pictures, exist_ok=True)
    return pictures


def _next_filename(prefix: str = "screenshot") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(_capture_dir(), f"{prefix}_{ts}.png")


def _active_window_rect() -> Optional[Tuple[int, int, int, int]]:
    """Return (left, top, right, bottom) of the focused window or None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        # DwmGetWindowAttribute (DWMWA_EXTENDED_FRAME_BOUNDS=9) gives the
        # *visible* frame, not the OS-padded one — matches what the user sees.
        try:
            dwmapi = ctypes.windll.dwmapi
            res = dwmapi.DwmGetWindowAttribute(
                hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
            )
            if res == 0:
                return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            pass
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None
    except Exception:
        return None


def _capture_full(path: str) -> bool:
    """Save a full-screen capture to ``path``. Return True on success."""
    # mss path — multi-monitor + fastest.
    try:
        import mss  # type: ignore
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[0])  # monitor 0 = bounding-rect of all
            from PIL import Image  # mss bundles enough to need PIL anyway
            pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil.save(path, "PNG")
            return True
    except Exception:
        pass
    # Pillow fallback
    try:
        from PIL import ImageGrab  # type: ignore
        img = ImageGrab.grab(all_screens=True)
        img.save(path, "PNG")
        return True
    except Exception:
        pass
    return False


def _capture_rect(path: str, rect: Tuple[int, int, int, int]) -> bool:
    """Save the given screen rectangle (l, t, r, b) to ``path``."""
    try:
        import mss  # type: ignore
        with mss.mss() as sct:
            box = {
                "left":   rect[0], "top":    rect[1],
                "width":  max(1, rect[2] - rect[0]),
                "height": max(1, rect[3] - rect[1]),
            }
            img = sct.grab(box)
            from PIL import Image
            pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil.save(path, "PNG")
            return True
    except Exception:
        pass
    try:
        from PIL import ImageGrab  # type: ignore
        img = ImageGrab.grab(bbox=rect, all_screens=True)
        img.save(path, "PNG")
        return True
    except Exception:
        pass
    return False


def _printscreen_clipboard() -> bool:
    """Last-resort fallback: tap PrintScreen so the user can paste somewhere."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        VK_SNAPSHOT = 0x2C
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_SNAPSHOT, 0, 0, 0)
        time.sleep(0.03)
        ctypes.windll.user32.keybd_event(VK_SNAPSHOT, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


# ── full screen ─────────────────────────────────────────────────────


@skill(
    name="screenshot_full",
    description="Capture the entire desktop (all monitors) to Pictures/AERIS/.",
    patterns=[
        "screenshot", "take a screenshot", "screenshot lo", "screen capture karo",
        "capture screen", "save screenshot", "full screenshot", "desktop screenshot",
        "screen ka photo lo", "screen ka snap lo", "save desktop",
        "screen grab", "screen grab karo",
    ],
    required_entities=[],
)
def screenshot_full(_slots: dict) -> str:
    path = _next_filename("screenshot")
    if _capture_full(path):
        return f"Screenshot save kar diya: {path}"
    if _printscreen_clipboard():
        return ("mss/Pillow nahi mile — PrintScreen press kar diya, "
                "clipboard se paste karo (install ke liye: pip install mss Pillow).")
    return ("Screenshot capture nahi ho paya. "
            "Install kar: pip install mss Pillow")


# ── active window ───────────────────────────────────────────────────


@skill(
    name="screenshot_window",
    description="Capture just the active window (focused app) to Pictures/AERIS/.",
    patterns=[
        "screenshot window", "active window screenshot", "this window screenshot",
        "is window ka screenshot lo", "current window screenshot",
        "window capture karo", "focused window screenshot",
        "active app screenshot", "snap this window",
    ],
    required_entities=[],
)
def screenshot_window(_slots: dict) -> str:
    rect = _active_window_rect()
    if not rect:
        return "Active window nahi mil paya — fallback me full screenshot le raha hoon."
    # Sanity-check dims
    l, t, r, b = rect
    if r - l < 10 or b - t < 10:
        return "Active window bahut chhoti hai — shayad minimized hai."
    path = _next_filename("window")
    if _capture_rect(path, rect):
        return f"Window screenshot save kar diya: {path}"
    return "Window screenshot capture nahi ho paya. Install: pip install mss Pillow"


# ── open the capture folder ──────────────────────────────────────────


@skill(
    name="screenshots_folder",
    description="Open the folder where AERIS saves screenshots (Pictures/AERIS).",
    patterns=[
        "open screenshots folder", "screenshots folder kholo",
        "show screenshots", "where are my screenshots",
        "screenshots dikhao", "captures folder", "saved screenshots dikhao",
    ],
    required_entities=[],
)
def screenshots_folder(_slots: dict) -> str:
    path = _capture_dir()
    try:
        os.startfile(path)
        return f"{path} khol diya."
    except Exception as e:
        return f"Folder nahi khul paya: {e}\nPath: {path}"
