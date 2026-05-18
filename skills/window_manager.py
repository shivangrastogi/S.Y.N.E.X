"""Window-management skills via raw Win32 (no extras needed).

Snap the active foreground window to standard positions on whichever
monitor it currently lives on. Honours the per-monitor *work area*
(i.e. doesn't draw over the taskbar) via ``SystemParametersInfoW``
SPI_GETWORKAREA on the relevant monitor.

Skills exposed:
  * ``snap left`` / ``snap right`` / ``snap top`` / ``snap bottom``
  * ``maximize`` / ``minimize`` / ``restore``
  * ``minimize all`` (Win+D show desktop)
  * ``close window``
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import sys

from core.skill_registry import skill

log = logging.getLogger(__name__)


# ── Win32 wrappers (lazy — module import must stay cheap on non-Windows) ─

_USER32 = None
if sys.platform == "win32":
    try:
        _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    except Exception as e:
        log.warning("[window_manager] user32 load failed: %s", e)


SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9


# ── Geometry helpers ───────────────────────────────────────────────── #

class _RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG),
                ("right", wt.LONG), ("bottom", wt.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", wt.DWORD)]


def _active_hwnd():
    if _USER32 is None:
        return None
    return _USER32.GetForegroundWindow() or None


def _work_area_for(hwnd) -> _RECT | None:
    """Return the *work area* (minus taskbar) of the monitor under hwnd."""
    if _USER32 is None or hwnd is None:
        return None
    MONITOR_DEFAULTTONEAREST = 2
    h_mon = _USER32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    if not _USER32.GetMonitorInfoW(h_mon, ctypes.byref(info)):
        return None
    return info.rcWork


def _move_window(hwnd, x, y, w, h) -> None:
    if _USER32 is None:
        return
    # Bring out of minimize if needed
    _USER32.ShowWindow(hwnd, SW_RESTORE)
    _USER32.MoveWindow(hwnd, int(x), int(y), int(w), int(h), True)


def _snap(half: str) -> str:
    if _USER32 is None:
        return "Window manager sirf Windows pe chalta hai."
    hwnd = _active_hwnd()
    if not hwnd:
        return "Active window detect nahi hua."
    wa = _work_area_for(hwnd)
    if wa is None:
        return "Monitor info nahi mila."
    w = wa.right - wa.left
    h = wa.bottom - wa.top
    if half == "left":
        _move_window(hwnd, wa.left,            wa.top, w // 2, h)
    elif half == "right":
        _move_window(hwnd, wa.left + w // 2,   wa.top, w - w // 2, h)
    elif half == "top":
        _move_window(hwnd, wa.left, wa.top,            w, h // 2)
    elif half == "bottom":
        _move_window(hwnd, wa.left, wa.top + h // 2,   w, h - h // 2)
    else:
        return f"Unknown snap target: {half}"
    return f"Window {half} half pe snap kar diya."


# ── Skills ─────────────────────────────────────────────────────────── #

@skill(
    name="window_snap_left",
    description="Snap the active window to the left half of its monitor",
    patterns=["snap left", "window left", "left half", "snap to left",
              "left side karo", "baayein"],
)
def window_snap_left(_slots: dict) -> str:
    return _snap("left")


@skill(
    name="window_snap_right",
    description="Snap the active window to the right half of its monitor",
    patterns=["snap right", "window right", "right half", "snap to right",
              "right side karo", "daayein"],
)
def window_snap_right(_slots: dict) -> str:
    return _snap("right")


@skill(
    name="window_snap_top",
    description="Snap the active window to the top half of its monitor",
    patterns=["snap top", "window top", "top half", "snap to top",
              "upar karo"],
)
def window_snap_top(_slots: dict) -> str:
    return _snap("top")


@skill(
    name="window_snap_bottom",
    description="Snap the active window to the bottom half of its monitor",
    patterns=["snap bottom", "window bottom", "bottom half", "snap to bottom",
              "neeche karo"],
)
def window_snap_bottom(_slots: dict) -> str:
    return _snap("bottom")


@skill(
    name="window_maximize",
    description="Maximize the active window",
    patterns=["maximize window", "maximize", "full screen window",
              "window bada karo", "pura kar do"],
)
def window_maximize(_slots: dict) -> str:
    if _USER32 is None:
        return "Window manager sirf Windows pe chalta hai."
    hwnd = _active_hwnd()
    if not hwnd:
        return "Active window detect nahi hua."
    _USER32.ShowWindow(hwnd, SW_MAXIMIZE)
    return "Window maximize kar diya."


@skill(
    name="window_minimize",
    description="Minimize the active window",
    patterns=["minimize window", "minimize", "hide window",
              "window chhupao", "chhota karo"],
)
def window_minimize(_slots: dict) -> str:
    if _USER32 is None:
        return "Window manager sirf Windows pe chalta hai."
    hwnd = _active_hwnd()
    if not hwnd:
        return "Active window detect nahi hua."
    _USER32.ShowWindow(hwnd, SW_MINIMIZE)
    return "Window minimize kar diya."


@skill(
    name="window_close",
    description="Close the active window (sends WM_CLOSE)",
    patterns=["close window", "close this", "band karo window",
              "kill window", "exit window"],
)
def window_close(_slots: dict) -> str:
    if _USER32 is None:
        return "Window manager sirf Windows pe chalta hai."
    hwnd = _active_hwnd()
    if not hwnd:
        return "Active window detect nahi hua."
    WM_CLOSE = 0x0010
    _USER32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return "Window close request bhej diya."


@skill(
    name="show_desktop",
    description="Minimize all windows (Win+D)",
    patterns=["show desktop", "desktop dikhao", "minimize all",
              "sab minimize", "clear screen"],
)
def show_desktop(_slots: dict) -> str:
    if _USER32 is None:
        return "Sirf Windows pe."
    # Win+D — toggles show-desktop.
    VK_LWIN = 0x5B
    VK_D = 0x44
    KEYEVENTF_KEYUP = 2
    _USER32.keybd_event(VK_LWIN, 0, 0, 0)
    _USER32.keybd_event(VK_D, 0, 0, 0)
    _USER32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
    _USER32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    return "Desktop dikha diya."
