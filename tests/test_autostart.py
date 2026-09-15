"""Tests for the login autostart manager.

Every test uses an in-memory fake registry — the real Windows registry is NEVER
touched — so this is safe to run anywhere.
"""

import os

import pytest

from core.autostart import (
    AutostartManager,
    RegistryBackend,
    standby_launch_command,
)


class _FakeRegistry(RegistryBackend):
    def __init__(self):
        self.store = {}

    def get(self, name):
        return self.store.get(name)

    def set(self, name, value):
        self.store[name] = value

    def delete(self, name):
        if name not in self.store:
            raise KeyError(name)
        del self.store[name]


def _mgr():
    reg = _FakeRegistry()
    return AutostartManager(app_name="AERIS Test", backend=reg), reg


# ── enable / disable ─────────────────────────────────────────────────── #

def test_starts_disabled():
    m, _ = _mgr()
    assert m.is_enabled() is False
    assert m.current_command() is None


def test_enable_registers_a_command():
    m, reg = _mgr()
    cmd = m.enable("do the thing --standby")
    assert cmd == "do the thing --standby"
    assert m.is_enabled() is True
    assert m.current_command() == "do the thing --standby"
    assert reg.store["AERIS Test"] == "do the thing --standby"


def test_enable_with_default_command_is_a_standby_launch():
    m, _ = _mgr()
    cmd = m.enable()
    assert "--standby" in cmd
    assert cmd.count('"') >= 2  # quoted exe + script


def test_enable_is_idempotent_overwrite():
    m, reg = _mgr()
    m.enable("first --standby")
    m.enable("second --standby")
    assert m.current_command() == "second --standby"
    assert len(reg.store) == 1


def test_disable_removes_and_reports_true():
    m, _ = _mgr()
    m.enable("x --standby")
    assert m.disable() is True
    assert m.is_enabled() is False


def test_disable_when_absent_is_safe_and_false():
    m, _ = _mgr()
    assert m.disable() is False  # nothing to remove, no raise


def test_enable_then_disable_round_trip():
    m, _ = _mgr()
    m.enable()
    assert m.is_enabled()
    m.disable()
    assert not m.is_enabled()
    assert m.current_command() is None


# ── launch command builder ───────────────────────────────────────────── #

def test_launch_command_shape():
    cmd = standby_launch_command(pythonw="C:\\py\\pythonw.exe",
                                 script="C:\\aeris\\main.py")
    assert cmd == '"C:\\py\\pythonw.exe" "C:\\aeris\\main.py" --standby'


def test_launch_command_defaults_point_at_main_and_standby():
    cmd = standby_launch_command()
    assert "--standby" in cmd
    assert cmd.strip().lower().endswith("--standby")
    assert "main.py" in cmd


def test_launch_command_windowless_false_uses_current_exe():
    import sys
    cmd = standby_launch_command(windowless=False, script="s.py")
    assert sys.executable in cmd
