"""Windows-only power-user utilities.

  * ``window_pin_top`` / ``window_unpin_top`` — toggle always-on-top on
    the foreground window via Win32 SetWindowPos.
  * ``summarize_window`` — copy active app + window title to clipboard.
  * ``whoami_info``      — user / host / IP / OS / uptime line.
  * ``wallpaper_set``    — set desktop wallpaper (file path or fuzzy lookup).
  * ``process_kill``     — kill a process by name via psutil.

Each skill no-ops gracefully on non-Windows / missing optional dep so the
module imports cleanly under pytest on a CI Linux box.
"""
from __future__ import annotations

import ctypes
import logging
import os
import platform
import re
import socket
import sys
import time
from pathlib import Path

from core.skill_registry import skill

log = logging.getLogger(__name__)


_IS_WIN = sys.platform == "win32"


# ── window_pin_top / window_unpin_top ──────────────────────────────


_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_SHOWWINDOW = 0x0040


def _set_topmost(topmost: bool) -> tuple[bool, str]:
    if not _IS_WIN:
        return False, "Skill sirf Windows pe chalti hai."
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return False, "Koi active window nahi mila."
        # Read title for the response message.
        length = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)
        title = (buf.value or "(no title)")[:60]
        flag = _HWND_TOPMOST if topmost else _HWND_NOTOPMOST
        ok = u32.SetWindowPos(hwnd, flag, 0, 0, 0, 0,
                              _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW)
        if not ok:
            return False, "SetWindowPos call fail ho gaya."
        return True, title
    except Exception as e:
        return False, f"Pin toggle fail: {e}"


@skill(
    name="window_pin_top",
    description="Make the foreground window always-on-top (Win32 HWND_TOPMOST).",
    patterns=[
        "pin window", "pin this window", "always on top",
        "window upar rakho", "window pin karo", "pin on top",
        "stick this window on top", "is window ko upar rakho",
        "topmost", "make this always on top",
    ],
    required_entities=[],
)
def window_pin_top(_slots: dict) -> str:
    ok, info = _set_topmost(True)
    if not ok:
        return info
    return f"Pinned on top: {info}"


@skill(
    name="window_unpin_top",
    description="Remove always-on-top from the foreground window.",
    patterns=[
        "unpin window", "unpin this window", "remove always on top",
        "window unpin karo", "stop topmost", "regular window karo",
        "untopmost", "remove pin", "unstick window",
    ],
    required_entities=[],
)
def window_unpin_top(_slots: dict) -> str:
    ok, info = _set_topmost(False)
    if not ok:
        return info
    return f"Unpinned: {info}"


# ── summarize_window ───────────────────────────────────────────────


def _foreground_info() -> tuple[str, str, int]:
    """Return (title, process_name, pid). All blank/0 on failure."""
    if not _IS_WIN:
        return "", "", 0
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return "", "", 0
        length = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""
        pid = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = ""
        try:
            import psutil  # type: ignore
            p = psutil.Process(int(pid.value))
            proc_name = p.name()
        except Exception:
            pass
        return title, proc_name, int(pid.value)
    except Exception as e:
        log.debug("[summarize_window] %s", e)
        return "", "", 0


@skill(
    name="summarize_window",
    description="Copy the active app's name and window title to clipboard.",
    patterns=[
        "summarize window", "what window am i on", "what app is open",
        "active window kya hai", "current window kya hai",
        "is window ka naam kya hai", "summarize active window",
        "what is in front", "kis app pe hoon", "kaunsi window khuli hai",
    ],
    required_entities=[],
)
def summarize_window(_slots: dict) -> str:
    title, proc, pid = _foreground_info()
    if not title and not proc:
        return "Active window nahi mil paya."
    label = f"{proc or '?'} (pid {pid}) — {title or '(no title)'}"
    # Push to clipboard if pyperclip is available.
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(label)
        return f"{label}\n(Clipboard mein copy bhi kar diya.)"
    except Exception:
        return label


# ── whoami_info ────────────────────────────────────────────────────


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "?"


def _uptime() -> str:
    try:
        import psutil  # type: ignore
        boot = psutil.boot_time()
        sec = int(time.time() - boot)
    except Exception:
        return "?"
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, _ = divmod(sec, 60)
    bits = []
    if d: bits.append(f"{d}d")
    if h or d: bits.append(f"{h}h")
    bits.append(f"{m}m")
    return " ".join(bits)


@skill(
    name="whoami_info",
    description="Quick identity: username, hostname, local IP, OS, uptime.",
    patterns=[
        "whoami", "who am i", "system identity",
        "my computer info", "mera system info", "user info",
        "host info", "kiska computer hai", "system details batao",
        "computer name", "what is my hostname",
    ],
    required_entities=[],
)
def whoami_info(_slots: dict) -> str:
    try:
        import getpass
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "?"
    host = platform.node() or "?"
    ip = _local_ip()
    osinfo = f"{platform.system()} {platform.release()}"
    up = _uptime()
    return (f"User: {user} · Host: {host} · IP: {ip} · "
            f"OS: {osinfo} · Uptime: {up}")


# ── wallpaper_set ──────────────────────────────────────────────────


_SPI_SETDESKWALLPAPER = 20
_SPIF_UPDATEINIFILE = 0x01
_SPIF_SENDCHANGE = 0x02


def _strip_wallpaper_verb(text: str) -> str:
    if not text:
        return ""
    s = re.sub(
        r"^(?:please\s+)?"
        r"(?:set|change|update)\s+(?:my\s+|the\s+)?(?:desktop\s+)?wallpaper"
        r"(?:\s+(?:to|file))?",   # optional "to" / "file" linker
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    # Hinglish suffix: "wallpaper change karo X" — strip trailing verb cluster.
    s = re.sub(r"^(.+?)\s+(?:change|set|update)\s+karo$", r"\1", s,
               flags=re.IGNORECASE)
    return s.strip(" \"',.?")


def _resolve_image_path(query: str) -> str | None:
    """Treat ``query`` as either an absolute path or a fuzzy name to look up
    under Pictures."""
    if not query:
        return None
    p = Path(os.path.expanduser(os.path.expandvars(query)))
    if p.is_file():
        return str(p)
    # Fuzzy: look under Pictures + Pictures/AERIS for any image whose name contains the query.
    pictures = Path.home() / "Pictures"
    candidates = []
    if pictures.exists():
        q = query.lower()
        for root, _dirs, files in os.walk(pictures):
            for fn in files:
                if fn.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                    if q in fn.lower():
                        full = Path(root) / fn
                        try:
                            mt = full.stat().st_mtime
                        except OSError:
                            mt = 0.0
                        candidates.append((mt, full))
            if len(candidates) >= 100:
                break
    if not candidates:
        return None
    candidates.sort(key=lambda t: -t[0])
    return str(candidates[0][1])


@skill(
    name="wallpaper_set",
    description="Set the Windows desktop wallpaper from a file path or a "
                "fuzzy name (looks under Pictures).",
    patterns=[
        "set wallpaper", "change wallpaper", "set my wallpaper to",
        "change desktop wallpaper", "wallpaper change karo",
        "background image set karo", "update wallpaper",
        "set wallpaper to", "wallpaper set karo",
    ],
    required_entities=[],
)
def wallpaper_set(slots: dict) -> str:
    if not _IS_WIN:
        return "Wallpaper skill sirf Windows pe chalti hai."
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_wallpaper_verb(text)
    if not query:
        return "Kaunsi image? Path do ya naam: 'set wallpaper to ocean.jpg'."
    path = _resolve_image_path(query)
    if not path:
        return f"'{query}' jaisi koi image Pictures mein nahi mili."
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            _SPI_SETDESKWALLPAPER, 0, path,
            _SPIF_UPDATEINIFILE | _SPIF_SENDCHANGE,
        )
        if not ok:
            return f"SystemParametersInfoW returned 0 — path: {path}"
        return f"Wallpaper set: {Path(path).name}"
    except Exception as e:
        return f"Wallpaper set fail: {e}"


# NOTE: process killing is handled by ``skills/productivity_extras.kill_process``.
# We don't ship a duplicate here — the existing handler already supports
# "kill chrome", "force quit", "terminate", etc. via the standard slot path.
