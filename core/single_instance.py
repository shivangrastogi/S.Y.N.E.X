"""Single-instance enforcement for the AERIS GUI.

Prevents two AERIS windows from launching at the same time. On a second
launch attempt we focus the existing window instead of starting a new
process.

Strategy
--------
Windows: ``CreateMutexW(name)`` + ``GetLastError() == ERROR_ALREADY_EXISTS``
is the canonical primitive — kernel-owned, auto-released on process exit,
survives PID reuse, no stale-file-lock pitfalls.

Cross-platform fallback: a lock-file with an advisory fcntl lock (POSIX)
or just a PID file (other OSes). The Windows path is what matters for
AERIS but the fallback keeps tests and smoke scripts portable.

Focusing the running window
---------------------------
We don't IPC — we just broadcast a custom ``WM_USER`` message addressed
to every top-level window whose title starts with ``A.E.R.I.S``. The
running instance hooks ``nativeEvent`` to listen for it and raises +
activates itself. Cheap, no socket setup, no port collisions.

Usage
-----
    from core.single_instance import SingleInstance
    inst = SingleInstance("aeris.gui")
    if inst.already_running():
        inst.signal_existing()
        sys.exit(0)
    # ... continue boot ...

The mutex handle is held by ``inst`` for the lifetime of the process —
keep the variable alive (typically as a module-global).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

log = logging.getLogger(__name__)


# Custom Windows message — high enough to avoid stomping on Qt internals.
# Anything in WM_USER..WM_USER+0x3FFF is reserved for app use; we pick a
# stable offset so a freshly launched instance and an old running one
# (potentially built from a slightly different commit) still agree on
# the wake-up code.
WM_AERIS_FOCUS = 0x0400 + 0x0EEE   # 0x0400 = WM_USER


class SingleInstance:
    """Holds the named mutex / lock-file for AERIS's lifetime."""

    def __init__(self, app_id: str = "aeris.gui"):
        self.app_id = app_id
        self._mutex = None
        self._lock_fd: Optional[int] = None
        self._lock_path: Optional[str] = None
        self._is_first: Optional[bool] = None

    # ── Acquire ─────────────────────────────────────────────────────

    def already_running(self) -> bool:
        """True iff another AERIS process holds the lock right now.

        Caches its result; safe to call repeatedly. On the first call
        we attempt to acquire the lock — if we get it we are the owner
        until ``release()`` or process exit.
        """
        if self._is_first is None:
            self._is_first = self._try_acquire()
        return not self._is_first

    def _try_acquire(self) -> bool:
        if sys.platform == "win32":
            return self._try_acquire_win32()
        return self._try_acquire_posix()

    def _try_acquire_win32(self) -> bool:
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            CreateMutexW = kernel32.CreateMutexW
            CreateMutexW.argtypes = [
                wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR
            ]
            CreateMutexW.restype = wintypes.HANDLE
            # ``Local\`` namespace = per-user session. Two users on the
            # same machine can each run their own AERIS without colliding.
            name = f"Local\\{self.app_id}.mutex"
            handle = CreateMutexW(None, False, name)
            ERROR_ALREADY_EXISTS = 183
            last_error = ctypes.get_last_error()
            if not handle:
                log.warning("[SingleInstance] CreateMutexW failed (err=%d) — "
                            "falling back to no-op (multi-launch possible).",
                            last_error)
                return True   # degrade open
            if last_error == ERROR_ALREADY_EXISTS:
                # We got a handle but the mutex was already owned —
                # someone else got there first.
                kernel32.CloseHandle(handle)
                return False
            self._mutex = handle
            return True
        except Exception as e:
            log.warning("[SingleInstance] win32 path failed (%s) — "
                        "falling back to file-lock.", e)
            return self._try_acquire_posix()

    def _try_acquire_posix(self) -> bool:
        # Portable fallback: open-with-O_EXCL on a lock file under
        # the user's temp dir. Sufficient for dev/smoke; not as
        # ironclad as a kernel mutex against crashes.
        import tempfile
        self._lock_path = os.path.join(tempfile.gettempdir(),
                                       f"{self.app_id}.lock")
        try:
            fd = os.open(self._lock_path,
                         os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
            os.write(fd, str(os.getpid()).encode())
            self._lock_fd = fd
            return True
        except FileExistsError:
            # Stale lock check — if the PID doesn't exist, take over.
            try:
                with open(self._lock_path) as f:
                    pid = int((f.read() or "0").strip())
                if pid > 0 and not _pid_alive(pid):
                    os.unlink(self._lock_path)
                    return self._try_acquire_posix()
            except Exception:
                pass
            return False

    # ── Release ─────────────────────────────────────────────────────

    def release(self) -> None:
        """Best-effort release. Called from atexit and graceful shutdown."""
        if self._mutex is not None:
            try:
                import ctypes
                ctypes.WinDLL("kernel32").CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None
        if self._lock_fd is not None:
            try:
                os.close(self._lock_fd)
            except Exception:
                pass
            self._lock_fd = None
        if self._lock_path and os.path.exists(self._lock_path):
            try:
                os.unlink(self._lock_path)
            except Exception:
                pass

    # ── Notify the running instance ─────────────────────────────────

    def signal_existing(self, title_prefix: str = "A.E.R.I.S") -> bool:
        """Post WM_AERIS_FOCUS to every visible top-level window whose
        title starts with ``title_prefix``. Best-effort; returns True if
        at least one message was posted.
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )
            IsWindowVisible = user32.IsWindowVisible
            GetWindowTextW = user32.GetWindowTextW
            GetWindowTextW.argtypes = [
                wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
            ]
            PostMessageW = user32.PostMessageW
            posted = [0]
            buf = ctypes.create_unicode_buffer(256)

            def _cb(hwnd, _lparam):
                if not IsWindowVisible(hwnd):
                    return True
                GetWindowTextW(hwnd, buf, 256)
                if buf.value.startswith(title_prefix):
                    PostMessageW(hwnd, WM_AERIS_FOCUS, 0, 0)
                    posted[0] += 1
                return True

            EnumWindows(EnumWindowsProc(_cb), 0)
            return posted[0] > 0
        except Exception as e:
            log.warning("[SingleInstance] signal_existing failed: %s", e)
            return False


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        # Best-effort guess on POSIX
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


# Auto-release on interpreter exit so a crash mid-boot doesn't leave a
# stale lock-file (the kernel mutex auto-releases either way).
import atexit as _atexit
_singleton: Optional[SingleInstance] = None


def acquire(app_id: str = "aeris.gui") -> SingleInstance:
    """Module-level convenience. Caches a single instance, registers
    atexit cleanup. Safe to call twice — returns the same instance.
    """
    global _singleton
    if _singleton is None:
        _singleton = SingleInstance(app_id)
        _atexit.register(_singleton.release)
    return _singleton


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    inst = acquire()
    if inst.already_running():
        print("Another AERIS instance is running. Asking it to focus...")
        ok = inst.signal_existing()
        print(f"signal_existing -> {ok}")
        sys.exit(0)
    print("This is the first/only AERIS instance. Sleeping 8s — try "
          "launching this script in another window now.")
    import time
    time.sleep(8)
