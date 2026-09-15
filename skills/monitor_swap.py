"""Move the active window between physical monitors.

Tries Win32 ``EnumDisplayMonitors`` to enumerate displays then ``MoveWindow``
to relocate the foreground window. Picks the next monitor in display order
relative to the one the window currently lives on.

Skills:
  * ``monitor_swap``     — move active window to the next monitor (cyclic)
  * ``monitor_list``     — list monitors with their virtual-screen rects
"""
from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import List, Tuple

from core.skill_registry import skill

log = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"


def _enum_monitors() -> List[Tuple[int, int, int, int]]:
    """Return [(left, top, right, bottom), ...] for every physical monitor."""
    if not _IS_WIN:
        return []
    results: list[Tuple[int, int, int, int]] = []
    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
    )

    def _cb(_hMon, _hdc, lprect, _data):
        r = lprect.contents
        results.append((r.left, r.top, r.right, r.bottom))
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_cb), 0)
    except Exception as e:
        log.warning("[monitor_swap] EnumDisplayMonitors failed: %s", e)
        return []
    return results


def _window_rect(hwnd: int) -> Tuple[int, int, int, int] | None:
    try:
        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return None


def _monitor_for_point(x: int, y: int, mons: list[Tuple[int, int, int, int]]) -> int:
    """Index of the monitor containing point (x,y), or 0."""
    for i, (l, t, r, b) in enumerate(mons):
        if l <= x < r and t <= y < b:
            return i
    return 0


# ── monitor_swap ───────────────────────────────────────────────────


@skill(
    name="monitor_swap",
    description="Move the active window to the next physical monitor.",
    patterns=[
        "monitor swap", "next monitor", "move to next monitor",
        "move window to other monitor", "window dusre monitor pe karo",
        "second monitor", "shift monitor", "switch monitor",
        "move to other screen", "window other screen",
        "window monitor change karo",
    ],
    required_entities=[],
)
def monitor_swap(_slots: dict) -> str:
    if not _IS_WIN:
        return "Monitor swap sirf Windows pe chalti hai."
    u32 = ctypes.windll.user32
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        return "Koi active window nahi mila."
    mons = _enum_monitors()
    if len(mons) <= 1:
        return f"Sirf {len(mons)} monitor detect hua — swap karne ke liye 2+ chahiye."
    wrect = _window_rect(hwnd)
    if not wrect:
        return "Window rect nahi mil paya."
    cx = (wrect[0] + wrect[2]) // 2
    cy = (wrect[1] + wrect[3]) // 2
    cur = _monitor_for_point(cx, cy, mons)
    nxt = (cur + 1) % len(mons)
    # Compute new position: same relative offset within the target monitor.
    l0, t0, r0, b0 = mons[cur]
    l1, t1, r1, b1 = mons[nxt]
    new_x = l1 + (wrect[0] - l0)
    new_y = t1 + (wrect[1] - t0)
    w = max(100, wrect[2] - wrect[0])
    h = max(100, wrect[3] - wrect[1])
    # Clamp inside target monitor.
    new_x = max(l1, min(r1 - w, new_x))
    new_y = max(t1, min(b1 - h, new_y))
    try:
        u32.MoveWindow(hwnd, new_x, new_y, w, h, True)
        return f"Window moved: monitor {cur + 1} → monitor {nxt + 1}"
    except Exception as e:
        return f"MoveWindow fail: {e}"


# ── monitor_list ───────────────────────────────────────────────────


@skill(
    name="monitor_list",
    description="List all physical monitors with their virtual-screen rectangles.",
    patterns=[
        "list monitors", "show monitors", "how many monitors",
        "monitors dikhao", "kitne monitors hain", "monitor count",
        "display info", "screens dikhao",
    ],
    required_entities=[],
)
def monitor_list(_slots: dict) -> str:
    if not _IS_WIN:
        return "Skill sirf Windows pe chalti hai."
    mons = _enum_monitors()
    if not mons:
        return "Koi monitor enumerate nahi hua."
    lines = [f"{len(mons)} monitor(s) detected:"]
    for i, (l, t, r, b) in enumerate(mons, 1):
        lines.append(f"  Monitor {i}: ({l},{t}) → ({r},{b})  size {r - l}×{b - t}")
    return "\n".join(lines)
