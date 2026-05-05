"""GUI entry point — launches the JARVIS v3.1 desktop app.

IMPORTANT: torch is pre-imported BEFORE PyQt5 to dodge a known Windows
WinError 1114 (DLL initialization failure) that surfaces when PyQt5 binds
its own MSVC runtime first and then torch tries to load conflicting CRT
DLLs from a worker thread. The pre-import is wrapped in try/except so the
GUI still launches even if torch is broken — the brain just stays unhealthy
and the logs panel surfaces the error.

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
# thread is busy importing sentence-transformers / spaCy. The brain
# thread runs at LowestPriority (see main_window._wire_workers) so the
# scheduler still favors the GUI; this just makes the GIL hand-off more
# responsive during the boot window.
sys.setswitchinterval(0.002)

# ── Pre-import torch to fix Windows DLL load order ─────────────────────
# Loading torch BEFORE Qt avoids 'WinError 1114: A dynamic link library
# (DLL) initialization routine failed' that some PyTorch+PyQt5 combos
# trigger on Windows when torch is imported on a worker thread.
try:
    import torch  # noqa: F401  -- intentional eager import
except Exception as _torch_err:
    # Don't crash the GUI; surface the error in stderr and let BrainWorker
    # report a clean failure when it tries to use the brain.
    sys.stderr.write(f"[run_gui] WARN: torch pre-import failed: {_torch_err}\n")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.jarvis_v31.main_window import launch


if __name__ == "__main__":
    sys.exit(launch())
