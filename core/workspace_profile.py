"""Foreground-app workspace classifier.

OS-concept demo
---------------
Windows exposes the active window via ``GetForegroundWindow`` →
``GetWindowThreadProcessId`` → ``psutil.Process(pid).name()``. Polling
every few seconds gives us a cheap heuristic for "what is the user
currently doing", which AERIS uses to:

  * Tune skill priority — e.g. when foreground is VSCode, prefer
    ``code_writer`` / git skills over media controls.
  * Suppress notifications during meetings (Zoom / Teams / Meet).
  * Mark sessions for the activity log (future).

Profiles
--------
  CODING   — VSCode, JetBrains IDEs, Sublime, Vim, terminal emulators
  MEETING  — Zoom, Teams, Google Meet (Chrome with `meet.google.com`
             URL — we can't read URL, so process-name only)
  BROWSING — chrome.exe, msedge.exe, firefox.exe, brave.exe (when not
             in a meeting client)
  GAMING   — Steam game launchers, common AAA executables, Discord +
             game combo
  MEDIA    — Spotify, VLC, mpc-hc, music players
  IDLE     — explorer.exe / lock screen / nothing in foreground

Signals
-------
``profile_changed(new_profile, foreground_proc_name)`` — fires only on
transitions, never every poll.
"""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


_POLL_INTERVAL_S = 5.0

PROFILE_CODING   = "CODING"
PROFILE_MEETING  = "MEETING"
PROFILE_BROWSING = "BROWSING"
PROFILE_GAMING   = "GAMING"
PROFILE_MEDIA    = "MEDIA"
PROFILE_IDLE     = "IDLE"

ALL_PROFILES = [PROFILE_CODING, PROFILE_MEETING, PROFILE_BROWSING,
                PROFILE_GAMING, PROFILE_MEDIA, PROFILE_IDLE]


# ── Heuristic process-name → profile map ───────────────────────────── #

_RULES: list[tuple[str, set[str]]] = [
    (PROFILE_MEETING, {
        "zoom.exe", "teams.exe", "ms-teams.exe", "skype.exe",
        "webexmta.exe", "googlemeet.exe", "discord.exe",
    }),
    (PROFILE_CODING, {
        "code.exe", "code - insiders.exe", "cursor.exe",
        "windsurf.exe", "idea64.exe", "pycharm64.exe",
        "studio64.exe", "rider64.exe", "clion64.exe",
        "phpstorm64.exe", "webstorm64.exe", "rubymine64.exe",
        "datagrip64.exe", "goland64.exe",
        "sublime_text.exe", "atom.exe",
        "gvim.exe", "nvim.exe", "vim.exe",
        "windowsterminal.exe", "wt.exe", "powershell.exe",
        "pwsh.exe", "cmd.exe", "alacritty.exe", "wezterm.exe",
        "devenv.exe",
    }),
    (PROFILE_GAMING, {
        "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe",
        "battle.net.exe", "leagueclient.exe", "valorant.exe",
        "csgo.exe", "cs2.exe", "dota2.exe", "minecraft.exe",
        "fortniteclient-win64-shipping.exe", "rocketleague.exe",
        "rdr2.exe", "gta5.exe",
    }),
    (PROFILE_MEDIA, {
        "spotify.exe", "vlc.exe", "mpc-hc.exe", "mpc-hc64.exe",
        "musicbee.exe", "foobar2000.exe", "wmplayer.exe",
    }),
    (PROFILE_BROWSING, {
        "chrome.exe", "msedge.exe", "firefox.exe",
        "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe",
    }),
]


def _classify_process(name: str) -> str:
    nm = (name or "").lower()
    for profile, stems in _RULES:
        if nm in stems:
            return profile
    return PROFILE_IDLE


# ── Foreground window probe ────────────────────────────────────────── #

def _foreground_process_name() -> str:
    if sys.platform != "win32":
        return ""
    try:
        user32 = ctypes.WinDLL("user32")
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        try:
            import psutil
            return psutil.Process(pid.value).name()
        except Exception:
            return ""
    except Exception:
        return ""


# ── Monitor ────────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class ProfileSnapshot:
    profile: str
    foreground: str
    since_ts: float


class WorkspaceProfileMonitor:
    """Daemon poller. Use ``get_monitor()`` for the process-wide instance."""

    def __init__(self, *, poll_interval_s: float = _POLL_INTERVAL_S):
        self._poll = max(1.0, poll_interval_s)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._snapshot = ProfileSnapshot(PROFILE_IDLE, "", time.time())
        self._subs: list[Callable[[str, str], None]] = []

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="WorkspaceMonitor", daemon=True
            )
            self._thread.start()

    def stop(self, *, timeout: float = 1.0) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)

    # ── Subscriptions ──────────────────────────────────────────────

    def subscribe(self, cb: Callable[[str, str], None]) -> Callable[[], None]:
        with self._lock:
            self._subs.append(cb)
        def _off():
            with self._lock:
                try: self._subs.remove(cb)
                except ValueError: pass
        return _off

    def snapshot(self) -> ProfileSnapshot:
        with self._lock:
            return self._snapshot

    # ── Internals ──────────────────────────────────────────────────

    def _run(self) -> None:
        if self._stop.wait(1.2):
            return
        while not self._stop.is_set():
            self._sample_once()
            if self._stop.wait(self._poll):
                return

    def _sample_once(self) -> None:
        name = _foreground_process_name()
        profile = _classify_process(name)
        fire: list[Callable[[str, str], None]] = []
        with self._lock:
            old = self._snapshot.profile
            if profile != old:
                self._snapshot = ProfileSnapshot(profile, name, time.time())
                fire = list(self._subs)
                log.info("[workspace] %s → %s (foreground=%s)",
                         old, profile, name or "?")
        for cb in fire:
            try: cb(profile, name)
            except Exception: log.exception("[workspace] sub raised")


_singleton: Optional[WorkspaceProfileMonitor] = None
_singleton_lock = threading.Lock()


def get_monitor() -> WorkspaceProfileMonitor:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = WorkspaceProfileMonitor()
        return _singleton


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    m = get_monitor()
    m._poll = 1.0
    m.subscribe(lambda p, n: print(f"  -> {p}  (fg={n})"))
    m.start()
    print("Sampling for 4s. Switch foreground window to see transitions.")
    time.sleep(4)
    s = m.snapshot()
    print(f"final: profile={s.profile} fg={s.foreground}")
    m.stop()
