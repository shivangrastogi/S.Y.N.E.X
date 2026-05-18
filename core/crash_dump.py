"""Uncaught-exception → crash-dump capture.

Installs hooks on:
  * ``sys.excepthook``           — main-thread crashes
  * ``threading.excepthook``     — worker-thread crashes (Python 3.8+)
  * ``sys.unraisablehook``       — GC/finaliser errors (Python 3.8+)

Each fires the same writer: a one-shot dump under
``data/logs/crash_<UTC timestamp>.txt`` containing:

  * Header — pid, time, python version, AERIS version
  * The full traceback that fired
  * All-thread stack traces (``threading.enumerate`` + ``sys._current_frames``)
  * The tail of ``data/logs/aeris.log`` (last 100 lines, if present)

The dump is also re-emitted to ``logging`` so it lands in the structured
log AND in the crash file — redundant but bullet-proof for postmortems.

We deliberately do not invoke the original excepthook after writing the
dump, except for the unraisable hook (where the GC will keep going
anyway). The shutdown coordinator's atexit hook still runs and flips
the crash beacon to ``clean_exit=True`` IF the interpreter survives —
in a hard segfault the beacon stays dirty and the next launch detects
the crash via the beacon path. Both signals reach the same surface.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import traceback
from typing import IO, Optional

log = logging.getLogger(__name__)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DUMP_DIR = os.path.join(_ROOT, "data", "logs")
_LOG_FILE = os.path.join(_DUMP_DIR, "aeris.log")

_installed = False
_install_lock = threading.Lock()


# ── Install / dump ─────────────────────────────────────────────────── #

def install() -> None:
    """Wire excepthooks. Idempotent."""
    global _installed
    with _install_lock:
        if _installed:
            return
        _installed = True

    os.makedirs(_DUMP_DIR, exist_ok=True)

    _original_excepthook = sys.excepthook
    def _main_hook(exc_type, exc, tb):
        try:
            _write_dump("main-thread", exc_type, exc, tb)
        except Exception:
            pass
        # Preserve default behaviour so Python still prints the traceback
        # to stderr and exits with the proper code.
        _original_excepthook(exc_type, exc, tb)
    sys.excepthook = _main_hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            try:
                _write_dump(f"thread:{args.thread.name}",
                            args.exc_type, args.exc_value, args.exc_traceback)
            except Exception:
                pass
            # Let the default handler still log to stderr.
            threading.__excepthook__(args)
        threading.excepthook = _thread_hook

    if hasattr(sys, "unraisablehook"):
        _orig_unraisable = sys.unraisablehook
        def _unraisable(args):
            try:
                _write_dump(f"unraisable:{args.object!r}",
                            args.exc_type, args.exc_value,
                            args.exc_traceback)
            except Exception:
                pass
            _orig_unraisable(args)
        sys.unraisablehook = _unraisable

    log.info("[crash_dump] installed (dumps → %s)", _DUMP_DIR)


def _write_dump(origin: str, exc_type, exc, tb) -> str:
    """Render a dump file. Returns the path written.

    Keeps everything inline so no other AERIS module is imported during
    the dump — minimises the chance of a cascading failure inside the
    error handler itself.
    """
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = os.path.join(_DUMP_DIR, f"crash_{ts}.txt")
    try:
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            _write_header(f, origin)
            _write_traceback(f, exc_type, exc, tb)
            _write_all_threads(f)
            _write_log_tail(f)
    except Exception as e:  # noqa: BLE001 — last-line of defence
        # If the file write fails, just route the dump through logging
        # so it's preserved in the rotating log.
        log.exception("[crash_dump] write failed (%s); rendering inline", e)
        try:
            log.error("[crash_dump:%s] %s: %s",
                      origin, exc_type.__name__, exc)
            log.error("[crash_dump:%s] traceback:\n%s",
                      origin, "".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:
            pass
        return ""
    log.error("[crash_dump] wrote %s for %s in %s",
              os.path.basename(path), exc_type.__name__ if exc_type else "?",
              origin)
    return path


# ── Renderers ──────────────────────────────────────────────────────── #

def _write_header(f: IO, origin: str) -> None:
    f.write(f"AERIS crash dump\n")
    f.write(f"  written : {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    f.write(f"  pid     : {os.getpid()}\n")
    f.write(f"  origin  : {origin}\n")
    f.write(f"  python  : {sys.version.splitlines()[0]}\n")
    f.write(f"  platform: {sys.platform}\n")
    f.write("\n")


def _write_traceback(f: IO, exc_type, exc, tb) -> None:
    f.write("=== Exception traceback ===\n")
    if exc_type is None:
        f.write("(no exception attached)\n\n")
        return
    f.write("".join(traceback.format_exception(exc_type, exc, tb)))
    f.write("\n")


def _write_all_threads(f: IO) -> None:
    f.write("=== All-thread stack traces ===\n")
    frames = sys._current_frames()
    by_id = {t.ident: t for t in threading.enumerate()}
    for tid, frame in frames.items():
        t = by_id.get(tid)
        label = f"thread {tid}"
        if t is not None:
            label += f"  name={t.name!r}  daemon={t.daemon}  alive={t.is_alive()}"
        f.write(label + "\n")
        f.write("".join(traceback.format_stack(frame)))
        f.write("\n")


def _write_log_tail(f: IO, *, lines: int = 100) -> None:
    f.write(f"=== Tail of {os.path.basename(_LOG_FILE)} (last {lines} lines) ===\n")
    if not os.path.exists(_LOG_FILE):
        f.write("(no log file present yet)\n")
        return
    try:
        with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as src:
            tail = src.readlines()[-lines:]
        f.write("".join(tail))
    except Exception as e:
        f.write(f"(could not read log: {e})\n")


# ── Convenience: trigger from outside, e.g. from a "test crash" menu ── #

def dump_now(label: str = "manual") -> str:
    """Force a dump of the current thread state — used for debugging.
    Returns the path written."""
    return _write_dump(f"manual:{label}", None, None, None)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    install()
    p = dump_now("smoke")
    print("manual dump at:", p)
    print()
    # Trigger a thread-level crash so the thread hook fires
    def _boom():
        raise RuntimeError("worker thread boom")
    t = threading.Thread(target=_boom, name="boom-thread")
    t.start()
    t.join()
    print("(check for crash_*.txt files in data/logs/)")
