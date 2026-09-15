"""Autonomous workspace tracker — builds a rolling timeline of what app
the user was focused on, who they spent time in, and totals per app.

A background thread samples the foreground window every ``_POLL_S`` (30 s
by default). Each unique exe gets accumulated duration; quick switches
between two apps don't pollute the timeline because a sample under
``_MIN_SLICE_S`` is folded into the surrounding interval.

Public API:
    tracker = get_workspace_tracker()
    tracker.start()
    tracker.stop()
    tracker.is_running()
    tracker.summary(window_s=3600) -> str
    tracker.recent_events(n=20)     -> list[dict]
    tracker.clear()
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)


_POLL_S = 30.0
_MIN_SLICE_S = 8.0       # below this, sample is merged with previous
_MAX_EVENTS = 2000       # rolling cap so the buffer doesn't grow forever


def _foreground_exe() -> str:
    """Return the foreground process exe name (lowercased). '' on failure."""
    try:
        import ctypes
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            import psutil  # type: ignore
            return (psutil.Process(int(pid.value)).name() or "").lower()
        except Exception:
            return ""
    except Exception:
        return ""


def _pretty_app(exe: str) -> str:
    """Convert 'code.exe' → 'VS Code', 'chrome.exe' → 'Chrome', etc."""
    if not exe:
        return "?"
    map_ = {
        "code.exe":         "VS Code",
        "chrome.exe":       "Chrome",
        "msedge.exe":       "Edge",
        "brave.exe":        "Brave",
        "firefox.exe":      "Firefox",
        "notepad.exe":      "Notepad",
        "explorer.exe":     "File Explorer",
        "discord.exe":      "Discord",
        "spotify.exe":      "Spotify",
        "slack.exe":        "Slack",
        "telegram.exe":     "Telegram",
        "outlook.exe":      "Outlook",
        "powershell.exe":   "PowerShell",
        "windowsterminal.exe": "Windows Terminal",
        "cmd.exe":          "Cmd",
        "winword.exe":      "Word",
        "excel.exe":        "Excel",
        "powerpnt.exe":     "PowerPoint",
        "obs64.exe":        "OBS",
        "teams.exe":        "Teams",
        "zoom.exe":         "Zoom",
        "python.exe":       "Python",
        "pythonw.exe":      "Python",
    }
    return map_.get(exe.lower(), exe.rsplit(".", 1)[0].title() or exe)


class WorkspaceTracker:
    def __init__(self):
        self._lock = threading.RLock()
        self._events: list[dict] = []   # [{ts, exe, duration_s}, ...]
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    # ── lifecycle ─────────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return True
            self._stop_evt.clear()
            self._thread = threading.Thread(
                target=self._loop, daemon=True, name="WorkspaceTracker",
            )
            self._thread.start()
            log.info("[workspace] tracker started (poll=%.1fs)", _POLL_S)
            return True

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        log.info("[workspace] tracker stopped.")

    # ── core loop ─────────────────────────────────────────────────

    def _loop(self) -> None:
        prev_exe: Optional[str] = None
        slice_start = time.monotonic()
        while not self._stop_evt.is_set():
            exe = _foreground_exe()
            now = time.monotonic()
            if prev_exe is None:
                prev_exe = exe
                slice_start = now
            elif exe != prev_exe:
                # Foreground app changed — close the previous slice.
                duration = now - slice_start
                if prev_exe and duration >= _MIN_SLICE_S:
                    self._append(prev_exe, duration)
                prev_exe = exe
                slice_start = now
            self._stop_evt.wait(_POLL_S)
        # Final flush on stop.
        now = time.monotonic()
        duration = now - slice_start
        if prev_exe and duration >= _MIN_SLICE_S:
            self._append(prev_exe, duration)

    def _append(self, exe: str, duration_s: float) -> None:
        with self._lock:
            self._events.append({
                "ts": time.time(),
                "exe": exe,
                "duration_s": float(duration_s),
            })
            # Roll the buffer if it's grown too large.
            if len(self._events) > _MAX_EVENTS:
                del self._events[: len(self._events) - _MAX_EVENTS]

    # ── query ─────────────────────────────────────────────────────

    def recent_events(self, n: int = 20) -> list[dict]:
        with self._lock:
            return list(self._events[-n:])

    def summary(self, window_s: float = 3600.0) -> str:
        cutoff = time.time() - window_s
        with self._lock:
            recent = [e for e in self._events if e["ts"] >= cutoff]
        if not recent:
            if not self.is_running():
                return ("Workspace tracker OFF — start with "
                        "'workspace track on'.")
            return "Abhi tak koi workspace activity record nahi hui."
        totals: dict[str, float] = defaultdict(float)
        for e in recent:
            totals[e["exe"]] += e["duration_s"]
        # Sort by total time descending.
        ranked = sorted(totals.items(), key=lambda kv: -kv[1])
        window_label = self._fmt_duration(window_s)
        lines = [f"Workspace summary · last {window_label} "
                 f"({len(recent)} switches):"]
        for exe, secs in ranked[:10]:
            lines.append(f"  • {_pretty_app(exe):20s} {self._fmt_duration(secs)}")
        return "\n".join(lines)

    def clear(self) -> int:
        with self._lock:
            n = len(self._events)
            self._events = []
        return n

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m"


_DEFAULT: Optional[WorkspaceTracker] = None


def get_workspace_tracker() -> WorkspaceTracker:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = WorkspaceTracker()
    return _DEFAULT
