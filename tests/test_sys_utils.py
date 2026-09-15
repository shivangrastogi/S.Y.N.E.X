"""System utilities — disk / process / uptime / keep-awake / recycle
(fast lane; psutil + ctypes faked, no real system mutation)."""

from __future__ import annotations

import sys
import types

import pytest

from core import sys_utils


class TestDisk:
    def test_specific_path(self, monkeypatch):
        monkeypatch.setattr(sys_utils.shutil, "disk_usage",
                            lambda p: types.SimpleNamespace(
                                total=500 * 1024**3, used=400 * 1024**3,
                                free=100 * 1024**3))
        out = sys_utils.disk_report("C:\\")
        assert "C:" in out and "100 GB free" in out and "20% free" in out
        assert "C::" not in out          # no double colon

    def test_tb_formatting(self, monkeypatch):
        monkeypatch.setattr(sys_utils.shutil, "disk_usage",
                            lambda p: types.SimpleNamespace(
                                total=4 * 1024**4, used=1 * 1024**4,
                                free=3 * 1024**4))
        assert "TB" in sys_utils.disk_report("D:\\")

    def test_all_drives_handles_error(self, monkeypatch):
        fake = types.SimpleNamespace(
            disk_partitions=lambda all=False: [
                types.SimpleNamespace(device="C:\\", mountpoint="C:\\",
                                      fstype="NTFS", opts="rw")],
            disk_usage=None)
        monkeypatch.setitem(sys.modules, "psutil", fake)
        monkeypatch.setattr(sys_utils.shutil, "disk_usage",
                            lambda p: types.SimpleNamespace(
                                total=100 * 1024**3, used=50 * 1024**3,
                                free=50 * 1024**3))
        out = sys_utils.disk_report()
        assert "C:" in out and "free" in out


class TestTopProcess:
    def _fake_psutil(self, procs):
        return types.SimpleNamespace(
            process_iter=lambda attrs=None: iter(procs),
            cpu_count=lambda: 8)

    def test_memory_aggregates_by_name(self, monkeypatch):
        procs = [
            types.SimpleNamespace(info={"name": "chrome.exe",
                "memory_info": types.SimpleNamespace(rss=200*1024**2),
                "cpu_percent": 0}),
            types.SimpleNamespace(info={"name": "chrome.exe",
                "memory_info": types.SimpleNamespace(rss=300*1024**2),
                "cpu_percent": 0}),
            types.SimpleNamespace(info={"name": "code.exe",
                "memory_info": types.SimpleNamespace(rss=100*1024**2),
                "cpu_percent": 0}),
        ]
        monkeypatch.setitem(sys.modules, "psutil", self._fake_psutil(procs))
        out = sys_utils.top_processes(5, "memory")
        assert "Top RAM" in out
        assert "chrome.exe 500MB" in out       # 200+300 aggregated
        assert out.index("chrome.exe") < out.index("code.exe")   # sorted

    def test_no_psutil_degrades(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "psutil", None)
        # importing None raises → the except path returns the message
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "psutil":
                raise ImportError("no psutil")
            return real_import(name, *a, **k)
        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert "psutil" in sys_utils.top_processes()


class TestUptime:
    def test_formats_days_hours(self, monkeypatch):
        fake = types.SimpleNamespace(boot_time=lambda: 0.0)
        monkeypatch.setitem(sys.modules, "psutil", fake)
        monkeypatch.setattr(sys_utils.time, "time",
                            lambda: 2 * 86400 + 3 * 3600 + 15 * 60)
        out = sys_utils.uptime_report()
        assert "2 din" in out and "3 ghante" in out and "15 minute" in out


class TestKeepAwake:
    def test_on_off_cycle_windows(self, monkeypatch):
        calls = []

        class _K32:
            def SetThreadExecutionState(self, flags):
                calls.append(flags)

        class _WinDLL:
            kernel32 = _K32()
        monkeypatch.setattr(sys_utils.os, "name", "nt")
        import ctypes
        monkeypatch.setattr(ctypes, "windll", _WinDLL(), raising=False)
        keeper = sys_utils._KeepAwake()
        assert keeper.on() is True and keeper.is_on() is True
        assert keeper.on() is True          # idempotent
        import time
        time.sleep(0.1)                     # let the daemon assert once
        assert keeper.off() is True and keeper.is_on() is False
        assert keeper.off() is False        # already off
        assert calls                        # at least the initial request

    def test_off_on_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys_utils.os, "name", "posix")
        keeper = sys_utils._KeepAwake()
        assert keeper.on() is False and keeper.is_on() is False


class TestRecycleBin:
    def test_success(self, monkeypatch):
        class _Shell:
            def SHEmptyRecycleBinW(self, a, b, flags):
                return 0

        class _WinDLL:
            shell32 = _Shell()
        monkeypatch.setattr(sys_utils.os, "name", "nt")
        import ctypes
        monkeypatch.setattr(ctypes, "windll", _WinDLL(), raising=False)
        assert "khali kar diya" in sys_utils.empty_recycle_bin()

    def test_already_empty(self, monkeypatch):
        class _Shell:
            def SHEmptyRecycleBinW(self, a, b, flags):
                return -2147418113          # 0x8000FFFF signed

        class _WinDLL:
            shell32 = _Shell()
        monkeypatch.setattr(sys_utils.os, "name", "nt")
        import ctypes
        monkeypatch.setattr(ctypes, "windll", _WinDLL(), raising=False)
        assert "pehle se hi khali" in sys_utils.empty_recycle_bin()

    def test_confirm_gated(self):
        from core.confirm_gate import needs_confirmation
        assert needs_confirmation("empty_recycle_bin")


class TestSkillWrappers:
    def test_disk_skill_extracts_drive(self, monkeypatch):
        monkeypatch.setattr(sys_utils, "disk_report",
                            lambda p=None: f"report:{p}")
        from skills.sys_utils_skill import disk_space
        assert disk_space({"raw_text": "c drive me kitni jagah hai"}) == \
               "report:C:\\"
        assert disk_space({"raw_text": "disk space batao"}) == "report:None"

    def test_top_process_picks_cpu(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(sys_utils, "top_processes",
                            lambda n=5, by="memory": seen.setdefault("by", by))
        from skills.sys_utils_skill import top_process
        top_process({"raw_text": "kaunsa app cpu kha raha hai"})
        assert seen["by"] == "cpu"
