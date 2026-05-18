"""Process-wide graceful-shutdown coordinator.

AERIS has many things to wind down on exit: brain worker QThreads, the
voice capture daemon, the TTS engine, the APScheduler, the resource
monitor, the feedback DB. Letting each subsystem race the interpreter
shutdown is fragile — we get sporadic "thread leaked" warnings, half-
flushed SQLite, occasional zombie pythonw.exe processes after a
crash, and lost in-flight work.

This module gives every subsystem one place to register a cleanup
callback. On shutdown they run in REVERSE registration order (last
registered = first torn down) with a bounded total wall-clock budget
so a wedged callback can't block exit forever.

Triggers
--------
* Qt's ``aboutToQuit`` signal (normal close)
* ``signal.SIGINT`` / ``signal.SIGBREAK`` / ``signal.SIGTERM`` (Ctrl-C,
  Ctrl-Break, kill from another process)
* ``atexit`` (catch-all for plain ``sys.exit``)

The handler is idempotent — multiple triggers fire it once.

Wiring
------
    from core.shutdown import register, install_handlers

    register("ResourceMonitor", lambda: get_monitor().stop(timeout=1))
    register("BrainThread", lambda: brain_thread.quit() or brain_thread.wait(2000))
    install_handlers()   # call once at boot

``register`` returns a deregistration closure for tests that want to
swap callbacks without polluting the global registry.
"""
from __future__ import annotations

import atexit
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class _Hook:
    name: str
    fn: Callable[[], None]
    timeout_s: float = 2.0


_hooks: list[_Hook] = []
_hooks_lock = threading.Lock()
_fired = False
_fire_lock = threading.Lock()

# Global wall-clock budget for the whole shutdown sequence. After this we
# stop waiting for slow callbacks and force-exit, because hanging at exit
# is worse than a half-clean teardown (the OS will reclaim everything).
_TOTAL_BUDGET_S = 8.0


def register(name: str,
             fn: Callable[[], None],
             *,
             timeout_s: float = 2.0) -> Callable[[], None]:
    """Register ``fn`` to run on shutdown. Returns a deregistration closure."""
    hook = _Hook(name=name, fn=fn, timeout_s=timeout_s)
    with _hooks_lock:
        _hooks.append(hook)
    def _unregister():
        with _hooks_lock:
            try: _hooks.remove(hook)
            except ValueError: pass
    return _unregister


def fire(reason: str = "manual") -> None:
    """Run every registered hook in reverse order. Safe to call any number
    of times; only the first call does work.
    """
    global _fired
    with _fire_lock:
        if _fired:
            return
        _fired = True

    log.info("[shutdown] firing (%s)", reason)
    started = time.monotonic()
    with _hooks_lock:
        ordered = list(reversed(_hooks))

    for hook in ordered:
        remaining_global = max(0.0, _TOTAL_BUDGET_S - (time.monotonic() - started))
        if remaining_global <= 0:
            log.warning("[shutdown] global budget exhausted, skipping %s", hook.name)
            continue
        budget = min(hook.timeout_s, remaining_global)
        _run_with_timeout(hook, budget)

    log.info("[shutdown] complete in %.2fs", time.monotonic() - started)


def _run_with_timeout(hook: _Hook, budget_s: float) -> None:
    """Run hook on a thread we can abandon if it overruns budget."""
    done = threading.Event()
    err: list[BaseException] = []

    def _runner():
        try:
            hook.fn()
        except BaseException as e:  # noqa: BLE001 — log everything
            err.append(e)
        finally:
            done.set()

    t = threading.Thread(target=_runner, name=f"shutdown:{hook.name}",
                         daemon=True)
    t0 = time.monotonic()
    t.start()
    if not done.wait(budget_s):
        log.warning("[shutdown] %s exceeded %.1fs budget — abandoning",
                    hook.name, budget_s)
        return
    dt = time.monotonic() - t0
    if err:
        log.warning("[shutdown] %s raised after %.2fs: %s",
                    hook.name, dt, err[0])
    else:
        log.debug("[shutdown] %s done in %.2fs", hook.name, dt)


# ── Signal + atexit wiring ─────────────────────────────────────────── #

_handlers_installed = False


def install_handlers() -> None:
    """Wire SIGINT / SIGBREAK / SIGTERM and atexit to ``fire()``.

    Safe to call multiple times; only the first call installs anything.
    """
    global _handlers_installed
    if _handlers_installed:
        return
    _handlers_installed = True

    def _on_signal(signum, _frame):
        try:
            name = signal.Signals(signum).name
        except Exception:
            name = str(signum)
        fire(reason=name)
        # Re-raise default behaviour so the process actually exits — without
        # this a Ctrl-C would just run hooks and then keep running. Use 130
        # as the standard "killed by SIGINT" exit code.
        if signum in (signal.SIGINT, getattr(signal, "SIGBREAK", None)):
            sys.exit(130)
        else:
            sys.exit(0)

    for sig_name in ("SIGINT", "SIGBREAK", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            # Some signals can't be installed from non-main threads or in
            # embedded interpreters; skip silently.
            pass

    atexit.register(lambda: fire(reason="atexit"))


def install_qt_handler(qapp) -> None:
    """Wire Qt's ``aboutToQuit`` so a normal window close also fires hooks.

    Called from ``launch()`` once the QApplication is constructed.
    """
    try:
        qapp.aboutToQuit.connect(lambda: fire(reason="aboutToQuit"))
    except Exception as e:
        log.warning("[shutdown] failed to wire aboutToQuit: %s", e)


# ── Diagnostics ────────────────────────────────────────────────────── #

def registered() -> list[str]:
    with _hooks_lock:
        return [h.name for h in _hooks]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    register("fast", lambda: print("  fast hook done"), timeout_s=1)
    register("medium", lambda: (time.sleep(0.3), print("  medium hook done"))[1], timeout_s=1)
    register("slow_overruns", lambda: (time.sleep(3), print("  slow done (should not print)"))[1], timeout_s=0.5)
    register("raises", lambda: (_ for _ in ()).throw(RuntimeError("boom")), timeout_s=1)
    print(f"registered: {registered()}")
    fire(reason="smoke")
    print("second fire (should be no-op):")
    fire(reason="smoke2")
