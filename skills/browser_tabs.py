"""Browser tab control — send keystrokes to the active window.

Most browsers (Chrome, Edge, Firefox, Brave, Vivaldi, Opera) share these
shortcuts, so a single skill set works across all of them.

SAFETY: keystrokes are sent ONLY when a known browser owns the foreground
window (``_BROWSER_PROCS`` guard in ``_ctrl``). Ctrl+W at a random focused
app closes documents without warning — with the guard, AERIS instead tells
you which app is in front and asks you to focus the browser.

Skills:
  * ``tab_switch`` — jump to tab N (1..9) via Ctrl+N. "tab 3" / "third tab"
  * ``tab_next`` / ``tab_prev`` — Ctrl+Tab / Ctrl+Shift+Tab
  * ``tab_close`` — Ctrl+W (NOTE: existing ``stroke_x`` also sends Ctrl+W;
    this is the explicit voice variant.)
  * ``tab_new``    — Ctrl+T
  * ``tab_reopen`` — Ctrl+Shift+T (undo close)
  * ``tab_pin``    — Chrome/Edge keyboard isn't standard — best-effort
                    via the right-click context menu chord (skipped).
"""
from __future__ import annotations

import ctypes
import logging
import re
import sys
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"

_VK_CONTROL = 0x11
_VK_SHIFT   = 0x10
_VK_TAB     = 0x09
_VK_W       = 0x57
_VK_T       = 0x54
_KEYEVENTF_KEYUP = 0x0002

_WORD_TO_DIGIT = {
    "first": 1, "1st": 1, "ek": 1, "pehla": 1,
    "second": 2, "2nd": 2, "do": 2, "dusra": 2, "doosra": 2,
    "third": 3, "3rd": 3, "teen": 3, "teesra": 3,
    "fourth": 4, "4th": 4, "chautha": 4,
    "fifth": 5, "5th": 5, "paanchva": 5,
    "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7,
    "eighth": 8, "8th": 8,
    "ninth": 9, "9th": 9, "last": 9,
}


def _press(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _release(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def _tap(vk: int) -> None:
    _press(vk); time.sleep(0.02); _release(vk)


# Processes we recognise as browsers. Tab keystrokes are ONLY sent when
# one of these owns the foreground window — Ctrl+W at a random focused
# app closes documents/panes with no warning (a user's unsaved editor
# nearly ate it this way; "usually a harmless no-op" was wrong).
_BROWSER_PROCS = {
    "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe",
    "opera.exe", "opera_gx.exe", "vivaldi.exe", "arc.exe", "iexplore.exe",
}

_LAST_BLOCK: str = ""


def _foreground_process() -> str:
    """Executable name of the process owning the foreground window."""
    try:
        from ctypes import wintypes
        import psutil
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return ""


def _fail_msg() -> str:
    return _LAST_BLOCK or "Keystroke send fail."


def _ctrl(vk: int, *, shift: bool = False) -> bool:
    global _LAST_BLOCK
    _LAST_BLOCK = ""
    if not _IS_WIN:
        return False
    fg = _foreground_process()
    if fg and fg not in _BROWSER_PROCS:
        _LAST_BLOCK = (f"Browser focused nahi hai — abhi {fg} saamne hai. "
                       f"Browser pe click karke dobara bolo.")
        log.info("[browser_tabs] blocked: foreground=%s", fg)
        return False
    try:
        _press(_VK_CONTROL)
        if shift:
            _press(_VK_SHIFT)
        try:
            _tap(vk)
        finally:
            if shift:
                _release(_VK_SHIFT)
            _release(_VK_CONTROL)
        return True
    except Exception as e:
        log.warning("[browser_tabs] keystroke failed: %s", e)
        return False


def _extract_tab_number(text: str) -> Optional[int]:
    """Pull 1..9 out of text. Accepts digits, ordinal words, Hinglish numbers."""
    if not text:
        return None
    t = text.lower()
    m = re.search(r"\btab\s*(\d)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d)(?:st|nd|rd|th)?\s+tab\b", t)
    if m:
        return int(m.group(1))
    for word, n in _WORD_TO_DIGIT.items():
        if re.search(rf"\b{re.escape(word)}\b", t):
            return n
    m = re.search(r"\b([1-9])\b", t)
    if m:
        return int(m.group(1))
    return None


# ── tab_switch ────────────────────────────────────────────────────


@skill(
    name="tab_switch",
    description="Jump to a numbered browser tab (Ctrl+1..9). Accepts digits, "
                "ordinal words (first / third / last), and Hinglish (pehla / dusra).",
    patterns=[
        "tab 1", "tab 2", "tab 3", "tab 4", "tab 5",
        "switch to tab", "jump to tab",
        "first tab", "second tab", "third tab", "fourth tab", "fifth tab",
        "last tab", "go to tab",
        "pehla tab kholo", "dusra tab kholo", "teesra tab kholo",
        "ek tab pe jao", "do tab pe jao",
    ],
    required_entities=[],
)
def tab_switch(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    n = _extract_tab_number(text)
    if n is None:
        return "Kaunsa tab? e.g. 'tab 3' or 'third tab'."
    if n < 1 or n > 9:
        return f"Tab number 1-9 hona chahiye (mila {n})."
    # Ctrl+1..9 — the digit VK codes are 0x31..0x39.
    vk = 0x30 + n
    if not _ctrl(vk):
        return _fail_msg()
    return f"Tab {n}."


# ── tab_next / tab_prev ───────────────────────────────────────────


@skill(
    name="tab_next",
    description="Switch to the next browser tab (Ctrl+Tab).",
    patterns=[
        "next tab", "tab next", "agla tab",
        "switch to next tab", "tab change", "tab change karo",
    ],
    required_entities=[],
)
def tab_next(_slots: dict) -> str:
    if not _ctrl(_VK_TAB):
        return _fail_msg()
    return "Next tab."


@skill(
    name="tab_prev",
    description="Switch to the previous browser tab (Ctrl+Shift+Tab).",
    patterns=[
        "previous tab", "prev tab", "tab prev", "pichla tab",
        "switch to previous tab", "go back tab",
    ],
    required_entities=[],
)
def tab_prev(_slots: dict) -> str:
    if not _ctrl(_VK_TAB, shift=True):
        return _fail_msg()
    return "Previous tab."


# ── tab_new / tab_close / tab_reopen ──────────────────────────────


@skill(
    name="tab_new",
    description="Open a new browser tab (Ctrl+T).",
    patterns=[
        "new tab", "open new tab", "naya tab kholo",
        "tab new", "fresh tab",
    ],
    required_entities=[],
)
def tab_new(_slots: dict) -> str:
    if not _ctrl(_VK_T):
        return _fail_msg()
    return "New tab."


@skill(
    name="tab_close",
    description="Close the current browser tab (Ctrl+W).",
    patterns=[
        "close tab", "close this tab", "ye tab band karo",
        "tab band karo", "close current tab",
    ],
    required_entities=[],
)
def tab_close(_slots: dict) -> str:
    if not _ctrl(_VK_W):
        return _fail_msg()
    return "Tab closed."


@skill(
    name="tab_reopen",
    description="Reopen the last closed tab (Ctrl+Shift+T).",
    patterns=[
        "reopen tab", "reopen closed tab", "undo close tab",
        "wapas kholo tab", "last tab wapas",
        "tab wapas kholo",
    ],
    required_entities=[],
)
def tab_reopen(_slots: dict) -> str:
    if not _ctrl(_VK_T, shift=True):
        return _fail_msg()
    return "Last closed tab reopened."
