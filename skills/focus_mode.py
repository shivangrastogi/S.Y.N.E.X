"""Focus mode — close distracting apps + enable Windows Do Not Disturb.

State machine
-------------
OFF (default)
   ↓  "focus mode on"
ON  — runs entry actions:
       1. List of currently-open distracting processes is saved to
          ``data/focus_mode_state.json`` (so we know what to restore).
       2. Each is terminated via ``psutil.Process.terminate()`` then,
          if still alive after 2 s, ``kill()``.
       3. Windows Focus Assist is set to PRIORITY ONLY via a registry
          tweak (best-effort — silently skipped if perms are wrong).
   ↓  "focus mode off"
OFF — restore actions:
       4. Re-open previously-closed apps from the saved state file.
       5. Reset Focus Assist to OFF.
       6. Delete the state file.

User can configure which apps count as "distracting" in
``data/settings.json``:

    focus_mode_close = ["discord", "slack", "telegram", "whatsapp", ...]
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import List

from core import settings as _settings
from core.atomic_io import write_atomic_json
from core.skill_registry import skill

log = logging.getLogger(__name__)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATE_PATH = os.path.join(_ROOT, "data", "focus_mode_state.json")


# ── State helpers ──────────────────────────────────────────────────── #

def _is_on() -> bool:
    return os.path.exists(_STATE_PATH)


def _save_state(closed: List[dict]) -> None:
    write_atomic_json(_STATE_PATH, {
        "closed": closed,
        "started_at": time.time(),
    })


def _load_state() -> dict:
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _clear_state() -> None:
    try:
        os.unlink(_STATE_PATH)
    except OSError:
        pass


# ── Action: close distracting apps ─────────────────────────────────── #

def _close_distracting() -> List[dict]:
    """Terminate processes whose ``name().lower()`` starts with any of
    the configured distractor stems. Returns a list of {"name", "exe"}
    we can later try to relaunch."""
    try:
        import psutil
    except ImportError:
        return []
    distractors = _settings.get("focus_mode_close",
                                ["discord", "slack", "telegram", "whatsapp"])
    closed: List[dict] = []
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            n = (proc.info.get("name") or "").lower()
            for stem in distractors:
                if n.startswith(stem.lower()):
                    closed.append({"name": proc.info.get("name") or stem,
                                   "exe": proc.info.get("exe") or ""})
                    proc.terminate()
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # Give graceful close 2 s, then escalate to kill.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        any_alive = False
        for proc in psutil.process_iter(["name"]):
            n = (proc.info.get("name") or "").lower()
            if any(n.startswith(s.lower()) for s in distractors):
                any_alive = True
                break
        if not any_alive:
            break
        time.sleep(0.2)
    for proc in psutil.process_iter(["name"]):
        try:
            n = (proc.info.get("name") or "").lower()
            if any(n.startswith(s.lower()) for s in distractors):
                proc.kill()
        except Exception:
            pass
    return closed


# ── Action: Focus Assist (Windows Notifications priority) ──────────── #

def _set_focus_assist(level: str) -> bool:
    """level in {"off","priority","alarms"}. Best-effort — returns
    True if the registry write succeeded, False otherwise.

    Note: Windows reads this registry value on a tight schedule; some
    builds still need user.dll RPC to fully apply. We accept the
    "registry-only" approximation here.
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg
        path = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings\Windows.SystemToast.QuietHours"
        mapping = {"off": 0, "priority": 1, "alarms": 2}
        v = mapping.get(level, 0)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as k:
            winreg.SetValueEx(k, "Enabled", 0, winreg.REG_DWORD, v)
        return True
    except Exception as e:
        log.debug("[focus_mode] Focus Assist registry failed: %s", e)
        return False


# ── Action: re-launch closed apps ──────────────────────────────────── #

def _relaunch(closed: List[dict]) -> int:
    n = 0
    for entry in closed:
        exe = entry.get("exe") or ""
        if exe and os.path.exists(exe):
            try:
                subprocess.Popen([exe], close_fds=True)
                n += 1
            except Exception as e:
                log.warning("[focus_mode] relaunch %s failed: %s", exe, e)
    return n


# ── Skills ─────────────────────────────────────────────────────────── #

@skill(
    name="focus_deep_on",
    description="Enter DEEP focus mode — close distracting apps + Windows DND",
    patterns=[
        "deep focus on", "deep work mode", "deep focus karo",
        "concentrate karo deep", "do not disturb on",
        "no distraction mode", "block all distractions",
    ],
)
def focus_deep_on(_slots: dict) -> str:
    if _is_on():
        return "Focus mode pehle se on hai."
    closed = _close_distracting()
    _save_state(closed)
    fa_ok = _set_focus_assist("priority")
    msg = f"Focus mode ON. {len(closed)} apps band kiye"
    if fa_ok:
        msg += " · Do Not Disturb set"
    msg += "."
    return msg


@skill(
    name="focus_deep_off",
    description="Exit DEEP focus mode — restore apps + clear DND",
    patterns=[
        "deep focus off", "stop deep focus", "exit deep focus",
        "do not disturb off", "distraction allowed",
        "deep focus band karo", "exit deep work",
    ],
)
def focus_deep_off(_slots: dict) -> str:
    if not _is_on():
        return "Focus mode abhi off hi hai."
    state = _load_state()
    closed = state.get("closed", [])
    n = _relaunch(closed)
    _set_focus_assist("off")
    _clear_state()
    return f"Focus mode OFF. {n} apps wapas chalu kiye."


@skill(
    name="focus_deep_status",
    description="Report whether DEEP focus mode is currently on",
    patterns=["deep focus status", "deep focus on hai kya",
              "is deep focus on", "deep focus kya hai"],
)
def focus_deep_status(_slots: dict) -> str:
    if _is_on():
        s = _load_state()
        n = len(s.get("closed", []))
        return f"Focus mode ON — {n} apps band hain."
    return "Focus mode off hai."
