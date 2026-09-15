"""Autostart manager — make AERIS standby launch at login.

An always-on assistant you have to start by hand isn't really always on. This
registers a Windows *Run* entry (``HKCU\\Software\\Microsoft\\Windows\\Current
Version\\Run``) that launches ``pythonw main.py --standby`` — windowless — when
the user logs in.

The manager is backend-agnostic: the real backend is ``winreg``, but every test
uses an in-memory fake so it never writes to the actual registry. The launch
command is built by ``standby_launch_command`` and is unit-tested on its own.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_DEFAULT_APP_NAME = "AERIS Standby"


# ── registry backends ────────────────────────────────────────────────── #

class RegistryBackend:
    """Read/write/delete a string value under the HKCU Run key."""

    def get(self, name: str) -> Optional[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def set(self, name: str, value: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def delete(self, name: str) -> None:  # pragma: no cover
        raise NotImplementedError


class WinRegBackend(RegistryBackend):
    """Real Windows registry backend (HKCU Run key)."""

    def __init__(self, run_key: str = _RUN_KEY) -> None:
        self._run_key = run_key

    def _winreg(self):
        import winreg  # only on Windows
        return winreg

    def get(self, name: str) -> Optional[str]:
        winreg = self._winreg()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._run_key) as k:
                val, _ = winreg.QueryValueEx(k, name)
                return val
        except FileNotFoundError:
            return None

    def set(self, name: str, value: str) -> None:
        winreg = self._winreg()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._run_key) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        winreg = self._winreg()
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, self._run_key, 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, name)


# ── launch command ───────────────────────────────────────────────────── #

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def standby_launch_command(*, pythonw: Optional[str] = None,
                           script: Optional[str] = None,
                           windowless: bool = True) -> str:
    """Build the command that autostart runs: ``"pythonw" "main.py" --standby``.

    Uses ``pythonw.exe`` (no console window) next to the current interpreter when
    available, so standby runs silently in the background.
    """
    if pythonw is None:
        exe = sys.executable
        if windowless:
            cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
            pythonw = cand if os.path.exists(cand) else exe
        else:
            pythonw = exe
    if script is None:
        script = os.path.join(_project_root(), "main.py")
    return f'"{pythonw}" "{script}" --standby'


# ── manager ──────────────────────────────────────────────────────────── #

class AutostartManager:
    """Enable/disable/query the login autostart entry."""

    def __init__(self, *, app_name: str = _DEFAULT_APP_NAME,
                 backend: Optional[RegistryBackend] = None) -> None:
        self._name = app_name
        self._backend = backend or WinRegBackend()

    def enable(self, command: Optional[str] = None) -> str:
        """Register the Run entry. Returns the command written."""
        cmd = command or standby_launch_command()
        self._backend.set(self._name, cmd)
        return cmd

    def disable(self) -> bool:
        """Remove the Run entry. Returns True if one was there, False if already
        absent. Never raises for an already-missing entry."""
        try:
            self._backend.delete(self._name)
            return True
        except (FileNotFoundError, KeyError, OSError):
            return False

    def is_enabled(self) -> bool:
        return self._backend.get(self._name) is not None

    def current_command(self) -> Optional[str]:
        return self._backend.get(self._name)
