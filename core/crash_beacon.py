"""Crash detection via a "clean exit" beacon file.

OS-concept demo
---------------
Every process needs a way to know whether its *previous* run exited
cleanly or was killed (segfault, OOM kill, power loss, force-kill from
Task Manager). Unix solves this with shells writing exit codes to
``$?``; long-running services solve it with PID files + supervisor
restarts (systemd's ``Restart=on-failure``). We do the simplest version
of the same idea, portable to Windows.

Algorithm
---------
On launch:
    1. Read ``data/last_boot.json`` if it exists.
    2. If the previous record's ``clean_exit`` is False *and* the recorded
       PID no longer exists, treat that as a crash → caller can show a
       "recovered from crash" banner, rotate logs, etc.
    3. Write a new record with the current PID + start_ts +
       clean_exit=False through ``atomic_io.write_atomic_json`` (so the
       beacon itself can't be corrupted mid-write).

On clean exit (called from shutdown coordinator):
    4. Rewrite the same record with clean_exit=True.

If step 4 never runs (crash, kill -9, power loss) the beacon stays
dirty and the *next* launch detects it. The atomic write in step 3
guarantees we never read a half-written beacon and falsely declare a
crash.

The beacon is intentionally tiny (a single JSON object) — opens cheaply
and survives full-disk situations because we always re-use the same
filename, never accumulate per-boot files.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Optional

from core.atomic_io import write_atomic_json

log = logging.getLogger(__name__)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "last_boot.json")


@dataclass
class BootRecord:
    pid: int
    start_ts: float
    clean_exit: bool
    version: str = "aeris-3.1"


@dataclass
class CrashReport:
    """Returned by ``check_previous_boot`` when the prior run is suspect."""
    previous: BootRecord
    confidence: str       # "high" (PID dead) | "medium" (PID alive but reused) | "low"


# ── Public surface ─────────────────────────────────────────────────── #

def check_previous_boot(path: str = _DEFAULT_PATH) -> Optional[CrashReport]:
    """Inspect the beacon left by the previous launch.

    Returns ``None`` if there was no previous record or the previous run
    exited cleanly. Returns a ``CrashReport`` if the previous beacon was
    dirty.
    """
    rec = _read(path)
    if rec is None or rec.clean_exit:
        return None
    return CrashReport(previous=rec, confidence=_classify_pid(rec.pid))


def mark_boot_start(path: str = _DEFAULT_PATH) -> None:
    """Write a new ``clean_exit=False`` record for the current PID.

    Should run as early as possible after the single-instance check so
    a crash during heavy boot is still detected as a crash, not a
    "never started".
    """
    rec = BootRecord(
        pid=os.getpid(),
        start_ts=time.time(),
        clean_exit=False,
    )
    try:
        write_atomic_json(path, asdict(rec))
    except OSError as e:
        # Disk-full or read-only filesystem — degrade gracefully.
        log.warning("[crash_beacon] could not write beacon (%s)", e)


def mark_clean_exit(path: str = _DEFAULT_PATH) -> None:
    """Flip ``clean_exit`` on the current beacon. Called from the
    shutdown coordinator's last hook so it runs after every other
    subsystem has drained.
    """
    rec = _read(path)
    if rec is None or rec.pid != os.getpid():
        # The beacon belongs to a different process or never existed;
        # nothing to flip.
        return
    try:
        rec.clean_exit = True
        write_atomic_json(path, asdict(rec))
    except OSError as e:
        log.warning("[crash_beacon] could not flip beacon (%s)", e)


# ── Internals ──────────────────────────────────────────────────────── #

def _read(path: str) -> Optional[BootRecord]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BootRecord(
            pid=int(data.get("pid", 0)),
            start_ts=float(data.get("start_ts", 0.0)),
            clean_exit=bool(data.get("clean_exit", False)),
            version=str(data.get("version", "unknown")),
        )
    except Exception as e:
        log.warning("[crash_beacon] beacon unreadable (%s) — ignoring", e)
        return None


def _classify_pid(pid: int) -> str:
    """Higher confidence the prior run actually crashed if its PID is dead.

    On Windows the OS reuses PIDs aggressively, so an "alive" PID doesn't
    *prove* the old run is still around — but it weakens our confidence.
    """
    if pid <= 0:
        return "low"
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return "high"
        # PID exists — could be the original (extremely rare given the
        # process-died-and-we-restarted scenario) or, more likely, the OS
        # already reissued the slot to someone else.
        return "medium"
    except Exception:
        return "low"


# ── Smoke test ─────────────────────────────────────────────────────── #

if __name__ == "__main__":
    import shutil
    import tempfile

    workdir = tempfile.mkdtemp(prefix="aeris_beacon_test_")
    p = os.path.join(workdir, "beacon.json")
    try:
        # Round 1: no previous record
        print("round 1 (no prior):", check_previous_boot(p))
        mark_boot_start(p)

        # Round 2: previous still dirty (simulated crash)
        cr = check_previous_boot(p)
        print(f"round 2 (after dirty start): {cr}")

        # Round 3: simulate clean exit, then check again
        mark_clean_exit(p)
        print("round 3 (after clean exit):", check_previous_boot(p))

        # Round 4: previous clean, write a new boot record, check
        mark_boot_start(p)
        cr = check_previous_boot(p)
        # Note: cr is still None because we just clean-exited in round 3
        # — the freshly-written round-4 record has clean_exit=False
        # (i.e. "in progress") which counts as a crash candidate. The
        # PID is ours though, so confidence comes back medium.
        print(f"round 4 (in-progress, same pid): {cr}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
