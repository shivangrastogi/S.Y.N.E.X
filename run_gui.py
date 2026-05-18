"""GUI entry point — launches the JARVIS v3.1 desktop app.

Boot sequence (Windows-tuned for no "Python not responding" dialog):

  1. torch import — MUST come BEFORE PyQt5 to dodge WinError 1114 (a
     dynamic link library initialization failure that some PyTorch +
     PyQt5 combos trigger on Windows when torch loads on a worker
     thread or after Qt has already loaded its CRT DLLs).

  2. BootSplash window — uses only PyQt5 core widgets so it appears
     within ~500 ms of process start. Once visible the OS marks the
     process as responsive and stops counting toward the "not
     responding" threshold even when subsequent imports briefly block
     the main thread.

  3. Heavy ML modules (sentence-transformers, sklearn, spaCy,
     transformers) imported on the MAIN thread while the splash is
     up. Doing it here — not inside BrainWorker on its QThread —
     means the worker sees them already in sys.modules and pays zero
     import cost; that eliminates the GIL spikes that would otherwise
     stutter the boot progress bar.

  4. Main window builds + shows, splash closes.

Older UI variants are still in:
  - ui/aeris_v4/main_window.py    (the previous AERIS layout)
  - ui/dashboard.py               (legacy dashboard)
"""
import os
import sys

# Fix duplicate OpenMP DLL conflict on Windows (torch + Qt both ship libiomp5md.dll)
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

# Halve the Python GIL switch interval (default 5 ms → 2 ms) so the GUI
# thread gets more frequent windows to repaint while the BrainWorker
# thread is busy. The brain thread runs at LowestPriority (see
# main_window._wire_workers) so the scheduler still favors the GUI;
# this just makes the GIL hand-off more responsive during the boot window.
sys.setswitchinterval(0.002)

# ── 1. Pre-import torch (must come BEFORE PyQt5) ───────────────────────
try:
    import torch  # noqa: F401  -- intentional eager import
except Exception as _torch_err:
    sys.stderr.write(f"[run_gui] WARN: torch pre-import failed: {_torch_err}\n")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ── 2. Get the splash on screen ASAP ───────────────────────────────────
from PyQt5.QtWidgets import QApplication

# Enforce single-instance BEFORE we paint anything — if AERIS is already
# running, the running copy gets a focus message and we exit cleanly.
# Done after the torch import so any DLL errors surface in the right
# process, but before the splash so we don't flash a second window.
from core.single_instance import acquire as _acquire_single_instance
_aeris_lock = _acquire_single_instance("aeris.gui")
if _aeris_lock.already_running():
    sys.stderr.write("[run_gui] AERIS already running — focusing existing window.\n")
    _aeris_lock.signal_existing()
    sys.exit(0)

# Install signal + atexit handlers as early as possible so even a crash
# during the heavy pre-imports below still runs the registered cleanup
# hooks (eg. releasing the single-instance mutex).
from core.shutdown import install_handlers as _install_shutdown_handlers
from core.shutdown import register as _register_shutdown_hook
_install_shutdown_handlers()

# Structured logging — configure root logger with rotating file sink so
# every subsystem from now on writes to data/logs/aeris.log automatically.
from core.log_setup import configure as _configure_logs, event as _log_event
_configure_logs()
_log_event("boot_start", pid=os.getpid())

# Uncaught-exception capture — every crash from now on dumps a
# crash_<ts>.txt with traceback + all-thread state + log tail. Installed
# AFTER logging so the dump renderer can reach the live log file.
from core import crash_dump as _crash_dump
_crash_dump.install()

# Crash beacon — write a "dirty" marker now so any crash during boot is
# detected on the next launch. The clean-exit flip is registered as the
# LAST shutdown hook (= first to run, because hooks fire in reverse) so
# we only mark clean after every other subsystem has drained.
from core import crash_beacon as _crash_beacon
_previous_crash = _crash_beacon.check_previous_boot()
if _previous_crash:
    sys.stderr.write(
        f"[run_gui] previous run did not exit cleanly "
        f"(pid={_previous_crash.previous.pid}, "
        f"confidence={_previous_crash.confidence})\n"
    )
    _log_event("crash_recovered",
               previous_pid=_previous_crash.previous.pid,
               previous_start_ts=_previous_crash.previous.start_ts,
               confidence=_previous_crash.confidence)
_crash_beacon.mark_boot_start()
_register_shutdown_hook("CrashBeacon", _crash_beacon.mark_clean_exit,
                        timeout_s=0.5)

from ui.jarvis_v31.splash import BootSplash

_app = QApplication.instance() or QApplication(sys.argv)
_splash = BootSplash()
_splash.show()
_app.processEvents()

# ── 3. Pre-import heavy ML modules with status updates ─────────────────
# Each entry is (module_import_path, splash_status_text, percent). Failures
# are logged but never raised — the brain worker will report a cleaner error
# downstream if a module is genuinely missing. Percents are advisory — they
# anchor the splash progress before the brain takes over at ~60 %.
_HEAVY_MODULES = [
    ("sentence_transformers", "Loading sentence-transformers", 15),
    ("sklearn.neighbors",     "Loading scikit-learn",          25),
    ("spacy",                 "Loading spaCy NLP runtime",     38),
    ("transformers",          "Loading HuggingFace transformers", 50),
]
for _mod, _label, _pct in _HEAVY_MODULES:
    _splash.update_status(f"{_label} ({_pct}%)")
    _app.processEvents()
    try:
        __import__(_mod)
    except Exception as _e:
        sys.stderr.write(f"[run_gui] WARN: {_mod} pre-import failed: {_e}\n")
    _app.processEvents()

_splash.update_status("Importing UI layer (55%)")
_app.processEvents()

from ui.jarvis_v31.main_window import launch


if __name__ == "__main__":
    sys.exit(launch(splash=_splash))
