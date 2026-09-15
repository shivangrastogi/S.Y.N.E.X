"""GUI entry point — launches the JARVIS v3.1 desktop app.

INSTANT-BOOT sequence (default):

  1. Cheap process plumbing only: env fixes, single-instance lock,
     shutdown handlers, structured logging, crash beacon. All of this
     is milliseconds — nothing heavy is imported yet.

  2. QApplication + main window constructed and SHOWN immediately.
     Target: window visible well under 1 second from process start.

  3. Everything heavy loads AFTER the window is on screen:
       - torch / sentence-transformers / sklearn / transformers are
         imported on the BrainWorker's QThread (LowestPriority) with a
         small sleep between phases so CPU load stays gentle — the
         boot is allowed to take ~a minute on weak laptops; what
         matters is the app FEELS open instantly and never lags.
       - Tray, hotkey, health server, skill watcher, workspace
         monitor, automation engine, semantic memory install one at a
         time on a staggered QTimer queue after first paint.

CLASSIC boot (the old order — torch BEFORE PyQt5, splash-first,
heavy imports on the main thread) is kept behind an env switch for
machines that hit the historical WinError 1114 torch/Qt DLL clash:

    set AERIS_CLASSIC_BOOT=1
    python run_gui.py

Older UI variants are still in:
  - ui/aeris_v4/main_window.py    (the previous AERIS layout)
  - ui/dashboard.py               (legacy dashboard)
"""
import os
import sys
import time

# pythonw.exe (no-console launch — AERIS.bat, detached Start-Process) gives
# sys.stdout/stderr == None. ANY later stderr.write / print (ours, pygame's
# banner, a library warning) would then raise AttributeError and crash the
# whole GUI at boot. Redirect them to a boot log BEFORE anything writes.
if sys.stdout is None or sys.stderr is None:
    try:
        _boot_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "data", "logs")
        os.makedirs(_boot_log_dir, exist_ok=True)
        _boot_sink = open(os.path.join(_boot_log_dir, "boot_stdio.log"),
                          "a", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        _boot_sink = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _boot_sink
    if sys.stderr is None:
        sys.stderr = _boot_sink

_T0 = time.perf_counter()   # process-start reference for boot timing

# Native-fault capture: Python excepthooks (crash_dump) only see *Python*
# exceptions. A segfault / access-violation in a native lib (torch, mediapipe,
# soundcard, SDL) kills the process silently — no crash_*.txt. faulthandler
# dumps a C-level, all-thread traceback to stderr (→ boot_stdio.log here) at the
# moment of the fault, which is the only way to diagnose such crashes.
try:
    import faulthandler as _fh
    _fh.enable(file=sys.stderr, all_threads=True)
except Exception:
    pass

# Fix duplicate OpenMP DLL conflict on Windows (torch + Qt both ship libiomp5md.dll)
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

# Heap-corruption guard (Windows fatal exception 0xc0000374 during a torch
# encode()'s .to()/convert): under the GUI's many concurrent threads, torch's
# MKL/OpenMP threadpool conflicts with the conda OpenMP runtime and corrupts
# the heap (text mode is single-threaded, so it never triggers there). Pinning
# the native math libs to one thread removes the conflicting threadpool. These
# MUST be set before torch/numpy/MKL are first imported. Our encoder is tiny —
# single-threaded encode is still fast. Override with AERIS_MATH_THREADS.
_math_threads = os.environ.get("AERIS_MATH_THREADS", "1")
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, _math_threads)

# Cap the OpenMP / MKL worker pools BEFORE torch/numpy load. Torch would
# otherwise spin up one thread per logical core and burn CPU on spin-waits
# — brutal on thin laptops with no dGPU. ONE thread: with
# KMP_DUPLICATE_LIB_OK a duplicate OpenMP runtime is loaded, and its
# parallel allocator corrupts the heap during torch tensor ops
# (Windows fatal 0xC0000374 inside model.to()/convert on encode —
# caught live). Single-threaded OpenMP has no parallel region to race,
# eliminating the corruption. AERIS only encodes short sentences, so the
# speed cost is nil.
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

# Tesseract OCR self-locate: the winget/UB-Mannheim installer updates the
# registry PATH, but a process launched from an old shell (or AERIS.bat)
# won't see it. If the default install exists, put it on THIS process's
# PATH so pytesseract (snip_ocr, vision, click_text) just works.
_TESS_DIR = r"C:\Program Files\Tesseract-OCR"
if os.path.isfile(os.path.join(_TESS_DIR, "tesseract.exe")) \
        and _TESS_DIR.lower() not in os.environ.get("PATH", "").lower():
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + _TESS_DIR

# Use the project's own tessdata (eng + hin + osd under data/models/)
# so Hinglish OCR works without admin rights on Program Files.
_TESSDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "models", "tessdata")
if os.path.isfile(os.path.join(_TESSDATA, "eng.traineddata")):
    os.environ.setdefault("TESSDATA_PREFIX", _TESSDATA)

# If the sentence-encoder is already in the local HuggingFace cache, force
# offline mode so huggingface_hub doesn't issue HEAD requests to hf.co on
# every boot. Without this, an offline / DNS-blocked machine hangs the
# brain load for ~30 s while HF retries (5 attempts with exponential
# backoff) before any cache fallback kicks in.
def _hf_model_cached(repo_id: str) -> bool:
    cache_root = os.environ.get("HF_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface", "hub"
    )
    folder = "models--" + repo_id.replace("/", "--")
    return os.path.isdir(os.path.join(cache_root, folder))

if (_hf_model_cached("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        and not os.environ.get("HF_HUB_OFFLINE")
        and not os.environ.get("HF_HUB_ONLINE_FORCE")):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Halve the Python GIL switch interval (default 5 ms → 2 ms) so the GUI
# thread gets more frequent windows to repaint while the BrainWorker
# thread is busy loading torch + the encoder in the background.
sys.setswitchinterval(0.002)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CLASSIC = os.environ.get("AERIS_CLASSIC_BOOT", "").strip() in ("1", "true", "yes")

# ── CLASSIC path only: pre-import torch BEFORE PyQt5 ───────────────────
# Dodges WinError 1114 on torch+Qt combos that can't load torch after Qt's
# CRT DLLs are resident.
#
# 2026-08-31 — this is NOT optional on every install. The note that used to
# live here ("verified to load torch cleanly on a worker thread under Qt on
# current installs") was measured on the Anaconda py3.13 environment, which
# has since been removed from this machine. On py3.10 + torch 2.10.0+cpu the
# instant path FAILS: importing torch on the BrainWorker thread after
# QApplication exists raises
#   OSError: [WinError 1114] ... Error loading torch\lib\c10.dll
# and the window opens but never accepts a command. Reproduced both ways in
# a two-line experiment: Qt-then-torch fails, torch-then-Qt succeeds.
#
# So on this machine either set AERIS_CLASSIC_BOOT=1, or run AERIS_LIGHT.bat
# (AERIS_SPLIT_BRAIN=1), where the GUI imports no torch at all and the child
# loads it on its own main thread with no Qt present — immune by construction.
# INSTANT path fix (2026-08-31): load torch's DLLs — not the Python package —
# before PyQt5. ~0.2 s versus ~1.6 s for a full `import torch`, so first paint
# stays fast and BrainWorker's later import on its own thread now succeeds.
# Skipped under AERIS_SPLIT_BRAIN, where this process never imports torch at
# all. Must happen BEFORE PyQt5: after QApplication exists the ctypes load
# fails with 1114 too. See core/torch_dll_preload.py.
if not _CLASSIC and os.environ.get("AERIS_SPLIT_BRAIN", "").strip().lower() \
        not in ("1", "true", "yes", "on"):
    try:
        from core.torch_dll_preload import preload_torch_dlls
        preload_torch_dlls()
    except Exception as _pre_err:
        sys.stderr.write(f"[run_gui] WARN: torch DLL preload skipped: {_pre_err}\n")

if _CLASSIC:
    try:
        import torch  # noqa: F401  -- intentional eager import
    except Exception as _torch_err:
        sys.stderr.write(f"[run_gui] WARN: torch pre-import failed: {_torch_err}\n")

# ── Cheap process plumbing (both paths) ────────────────────────────────

# Spawn-safety: multiprocessing 'spawn' re-imports this file as "__mp_main__"
# in worker children (e.g. the isolated brain when AERIS_SPLIT_BRAIN=1). Those
# children must NOT run the GUI boot plumbing below (single-instance exit, Qt
# app, crash beacon, log sink) — they only need the pickled target from core.*.
# When launched normally this file IS __main__, so _IS_MAIN is True and every
# statement below runs exactly as before; only spawned children skip it.
_IS_MAIN = (__name__ == "__main__")

# Enforce single-instance BEFORE we paint anything — if AERIS is already
# running, the running copy gets a focus message and we exit cleanly.
from core.single_instance import acquire as _acquire_single_instance
_aeris_lock = _acquire_single_instance("aeris.gui") if _IS_MAIN else None
if _IS_MAIN and _aeris_lock.already_running():
    # Another process holds the lock. Prefer to surface ITS window and bow
    # out — but a lock held by a hung/windowless zombie (window closed yet
    # the process lingers, or frozen mid-op) is the classic "AERIS won't
    # open" trap: the old code posted a focus message to a window that
    # wasn't there and exited anyway, so the user saw *nothing*. Now we
    # only defer if the existing instance is actually reachable — a
    # focusable window OR a live /health endpoint. Otherwise assume it's
    # stale and boot anyway (the single-instance lock is advisory).
    from core.single_instance import existing_is_responsive as _existing_alive
    if _aeris_lock.signal_existing():
        sys.stderr.write("[run_gui] AERIS already running — focused existing window.\n")
        sys.exit(0)
    if _existing_alive():
        sys.stderr.write("[run_gui] AERIS already running (health OK, no top-level "
                         "window found) — deferring to it.\n")
        sys.exit(0)
    sys.stderr.write("[run_gui] single-instance lock held but no live AERIS window or "
                     "health endpoint answered — treating it as stale/hung and "
                     "launching anyway.\n")
    # Fall through and boot normally.

# Boot plumbing — imports stay module-level (harmless, and the _boot_*
# functions reference _log_event / _register_shutdown_hook); the side-effecting
# CALLS are gated on _IS_MAIN so a spawned brain child neither installs a second
# log sink / crash handler on the same files nor pollutes the GUI's crash beacon.
from core.shutdown import install_handlers as _install_shutdown_handlers
from core.shutdown import register as _register_shutdown_hook
from core.log_setup import configure as _configure_logs, event as _log_event
from core import crash_dump as _crash_dump
from core import crash_beacon as _crash_beacon

if _IS_MAIN:
    # Install signal + atexit handlers as early as possible so even a crash
    # during boot still runs the registered cleanup hooks (eg. releasing the
    # single-instance mutex).
    _install_shutdown_handlers()

    # Structured logging — rotating file sink so every subsystem writes to
    # data/logs/aeris.log automatically.
    _configure_logs()
    _log_event("boot_start", pid=os.getpid(), classic=_CLASSIC)

    # Uncaught-exception capture — every crash from now on dumps a
    # crash_<ts>.txt with traceback + all-thread state + log tail.
    _crash_dump.install()

    # Crash beacon — write a "dirty" marker now so any crash during boot is
    # detected on the next launch. The clean-exit flip is registered as the
    # LAST shutdown hook (= first to run, because hooks fire in reverse) so
    # we only mark clean after every other subsystem has drained.
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

# ── Qt up ───────────────────────────────────────────────────────────────
# Import PyQt5 ONLY in the real GUI process. A spawned worker child (the
# isolated brain, AERIS_SPLIT_BRAIN=1) re-imports this module as __mp_main__
# and needs no GUI toolkit — skipping the ~1–2 s PyQt5 import there keeps the
# child lean and its split-boot faster.
if _IS_MAIN:
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication(sys.argv)
else:
    _app = None


def _boot_classic():
    """The original splash-first boot: heavy ML imports on the main
    thread while a splash animates; window shown only when the brain
    is fully ready. Kept for machines with the torch/Qt DLL clash."""
    from ui.jarvis_v31.splash import BootSplash
    splash = BootSplash()
    splash.show()
    _app.processEvents()

    heavy = [
        ("sentence_transformers", "Loading sentence-transformers", 15),
        ("sklearn.neighbors",     "Loading scikit-learn",          25),
        ("spacy",                 "Loading spaCy NLP runtime",     38),
        ("transformers",          "Loading HuggingFace transformers", 50),
    ]
    for mod, label, pct in heavy:
        splash.update_status(f"{label} ({pct}%)")
        _app.processEvents()
        try:
            __import__(mod)
        except Exception as e:
            sys.stderr.write(f"[run_gui] WARN: {mod} pre-import failed: {e}\n")
        _app.processEvents()

    splash.update_status("Importing UI layer (55%)")
    _app.processEvents()
    from ui.jarvis_v31.main_window import launch
    return launch(splash=splash)


def _boot_instant():
    """Instant boot: window on screen first, everything heavy after."""
    from ui.jarvis_v31.main_window import launch
    _log_event("window_launching",
               elapsed_ms=round((time.perf_counter() - _T0) * 1000, 1))
    return launch(splash=None, boot_t0=_T0)


if __name__ == "__main__":
    sys.exit(_boot_classic() if _CLASSIC else _boot_instant())
