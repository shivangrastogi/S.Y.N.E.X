"""Local system utilities — disk, processes, uptime, keep-awake, recycle bin.

Pure on-device: psutil for readings, ctypes for Windows power/shell APIs.
No network, no external service. Backs ``skills/sys_utils_skill.py``.
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)


# ── disk ─────────────────────────────────────────────────────────────── #

def _fmt_gb(n_bytes: float) -> str:
    gb = n_bytes / (1024 ** 3)
    if gb >= 1024:
        return f"{gb / 1024:.1f} TB"
    return f"{gb:.0f} GB"


def disk_report(path: Optional[str] = None) -> str:
    """Free/total for one path, or every fixed drive when path is None."""
    try:
        if path:
            u = shutil.disk_usage(path)
            pct = u.free / u.total * 100 if u.total else 0
            label = os.path.splitdrive(path)[0] or path   # "C:" already
            return (f"{label} {_fmt_gb(u.free)} free of {_fmt_gb(u.total)} "
                    f"({pct:.0f}% free).")
        import psutil
        parts = []
        for p in psutil.disk_partitions(all=False):
            if "cdrom" in p.opts or not p.fstype:
                continue
            try:
                u = shutil.disk_usage(p.mountpoint)
            except Exception:
                continue
            pct = u.free / u.total * 100 if u.total else 0
            parts.append(f"{p.device.rstrip(chr(92))} {_fmt_gb(u.free)} free "
                         f"/ {_fmt_gb(u.total)} ({pct:.0f}%)")
        return "  ·  ".join(parts) if parts else "Koi drive nahi mila."
    except Exception as e:
        log.debug("[sys_utils] disk_report failed: %s", e)
        return "Disk info nahi mila abhi."


# ── processes ────────────────────────────────────────────────────────── #

def top_processes(n: int = 5, by: str = "memory") -> str:
    """Top-N processes by memory (default) or CPU, aggregated per name."""
    try:
        import psutil
    except Exception:
        return "psutil available nahi — process info nahi de paunga."
    agg: dict[str, float] = {}
    if by == "cpu":
        # Prime cpu_percent (first read is always 0), then measure.
        for p in psutil.process_iter():
            try:
                p.cpu_percent(None)
            except Exception:
                pass
        time.sleep(0.4)
    for p in psutil.process_iter(["name", "memory_info", "cpu_percent"]):
        try:
            name = (p.info.get("name") or "?").lower()
            if by == "cpu":
                val = p.info.get("cpu_percent") or 0.0
            else:
                mi = p.info.get("memory_info")
                val = (mi.rss / (1024 ** 2)) if mi else 0.0   # MB
            agg[name] = agg.get(name, 0.0) + val
        except Exception:
            continue
    if not agg:
        return "Process list nahi mili."
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:n]
    if by == "cpu":
        ncpu = psutil.cpu_count() or 1
        rows = [f"{nm} {min(100.0, v / ncpu):.0f}%" for nm, v in top]
        return "Top CPU: " + " · ".join(rows)
    rows = [f"{nm} {v:.0f}MB" for nm, v in top]
    return "Top RAM: " + " · ".join(rows)


# ── uptime ───────────────────────────────────────────────────────────── #

def uptime_report() -> str:
    try:
        import psutil
        secs = time.time() - psutil.boot_time()
    except Exception:
        return "Uptime nahi nikal paya."
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d} din")
    if h:
        parts.append(f"{h} ghante")
    parts.append(f"{m} minute")
    return "Computer " + " ".join(parts) + " se on hai."


# ── keep awake (SetThreadExecutionState via a persistent keeper) ─────── #

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


class _KeepAwake:
    """Prevents sleep/display-off until turned off.

    The execution-state request is thread-scoped on Windows, so a
    short-lived skill-call thread setting it would lose the request the
    moment it returns. We hold it on a dedicated daemon thread that stays
    alive for the whole 'awake' window — genuinely robust, not a one-shot.
    """

    def __init__(self):
        self._on = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def is_on(self) -> bool:
        return self._on

    def on(self) -> bool:
        with self._lock:
            if self._on:
                return True
            if os.name != "nt":
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._hold, name="KeepAwake", daemon=True)
            self._thread.start()
            self._on = True
            return True

    def off(self) -> bool:
        with self._lock:
            if not self._on:
                return False
            self._stop.set()
            self._on = False
            return True

    def _hold(self):
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED)
            # Re-assert every 50s (belt-and-suspenders) until told to stop.
            while not self._stop.wait(50):
                k32.SetThreadExecutionState(
                    _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED)
        except Exception as e:
            log.debug("[sys_utils] keep-awake hold failed: %s", e)
        finally:
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
            except Exception:
                pass


_KEEPER = _KeepAwake()


def keep_awake(on: bool) -> bool:
    return _KEEPER.on() if on else _KEEPER.off()


def keep_awake_status() -> bool:
    return _KEEPER.is_on()


# ── recycle bin ──────────────────────────────────────────────────────── #

def empty_recycle_bin() -> str:
    """Empty the Windows Recycle Bin (SHEmptyRecycleBinW). Irreversible —
    the skill is confirm-gated upstream."""
    if os.name != "nt":
        return "Recycle bin sirf Windows par."
    try:
        import ctypes
        # flags: no confirm dialog | no progress UI | no sound
        SHERB_NOCONFIRMATION = 0x1
        SHERB_NOPROGRESSUI = 0x2
        SHERB_NOSOUND = 0x4
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None,
            SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
        # 0 = success, 0x8000FFFF (E_UNEXPECTED) = already empty.
        if res == 0:
            return "Recycle bin khali kar diya, sir."
        if res & 0xFFFFFFFF == 0x8000FFFF:
            return "Recycle bin pehle se hi khali tha."
        return f"Recycle bin khali karne mein issue (code {res})."
    except Exception as e:
        log.debug("[sys_utils] empty recycle failed: %s", e)
        return "Recycle bin khali nahi kar paya."
