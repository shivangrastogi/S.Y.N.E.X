"""torch DLL preload — keeps instant boot AND fixes WinError 1114.

On Windows, once Qt's CRT DLLs are resident some torch builds can no longer
initialise theirs. AERIS's instant-boot path imports PyQt5 first and lets
BrainWorker import torch later on its own thread — exactly the failing order.
On py3.10 + torch 2.10.0+cpu the window opened and then never accepted a
command.

Measured three ways:

    PyQt5 -> QApplication -> torch (worker)     WinError 1114
    torch -> PyQt5 -> QApplication              works, ~1.6 s
    ctypes preload -> PyQt5 -> torch (worker)   works, ~0.2 s

so `run_gui.py` loads torch's DLLs (not the package) before importing Qt.

This file imports neither torch nor PyQt5 — `torch_lib_dir()` deliberately
uses `find_spec`, which locates a package without executing it.
"""

from __future__ import annotations

import os
import sys

import pytest

from core import torch_dll_preload as tdp


@pytest.fixture(autouse=True)
def _reset_one_shot():
    """The module is a one-shot; tests need a clean slate each time."""
    original = tdp._done
    tdp._done = False
    yield
    tdp._done = original


# --------------------------------------------------------------------- #
#  Locating torch without importing it                                   #
# --------------------------------------------------------------------- #

def test_lib_dir_found_without_importing_torch(monkeypatch):
    """Importing torch here would defeat the purpose — and in the GUI would
    be the very thing that fails."""
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    lib = tdp.torch_lib_dir()
    if lib is None:
        pytest.skip("torch not installed in this interpreter")
    assert os.path.isdir(lib)
    assert os.path.basename(lib) == "lib"


def test_lib_dir_none_when_torch_absent(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    assert tdp.torch_lib_dir() is None


def test_lib_dir_survives_a_raising_find_spec(monkeypatch):
    """A weird import hook must not take the GUI's boot down."""
    def boom(name):
        raise RuntimeError("import machinery is unhappy")

    monkeypatch.setattr("importlib.util.find_spec", boom)
    assert tdp.torch_lib_dir() is None


def test_lib_dir_none_when_spec_has_no_search_locations(monkeypatch):
    class _Spec:
        submodule_search_locations = None

    monkeypatch.setattr("importlib.util.find_spec", lambda name: _Spec())
    assert tdp.torch_lib_dir() is None


# --------------------------------------------------------------------- #
#  The preload itself                                                    #
# --------------------------------------------------------------------- #

def test_preload_is_a_one_shot(monkeypatch):
    calls = []
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: calls.append(1) or None)
    tdp.preload_torch_dlls()
    tdp.preload_torch_dlls()
    assert len(calls) == 1, "preload must not redo its work on every call"


def test_preload_noop_without_torch(monkeypatch):
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: None)
    assert tdp.preload_torch_dlls() is False


def test_preload_noop_off_windows(monkeypatch):
    """`os.add_dll_directory` and `ctypes.WinDLL` are Windows-only."""
    monkeypatch.setattr(sys, "platform", "linux")
    called = []
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: called.append(1) or "/x")
    assert tdp.preload_torch_dlls() is False
    assert called == []


def test_preload_skips_missing_dlls(monkeypatch, tmp_path):
    """A future torch that renames or drops a DLL must degrade to 'did
    nothing', never raise into the boot path."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: str(tmp_path))
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    assert tdp.preload_torch_dlls() is False      # nothing on disk to load


def test_preload_survives_a_dll_that_refuses_to_load(monkeypatch, tmp_path):
    """This is the 'called too late, Qt already up' case: c10.dll itself
    raises 1114. It must be swallowed so BrainWorker's own import reports the
    real error instead."""
    import ctypes

    for name in tdp._DLLS:
        (tmp_path / name).write_bytes(b"not a real dll")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: str(tmp_path))
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)

    def refuse(path):
        raise OSError("[WinError 1114] DLL initialization routine failed")

    monkeypatch.setattr(ctypes, "WinDLL", refuse, raising=False)
    assert tdp.preload_torch_dlls() is False      # must not raise


def test_preload_reports_success_when_dlls_load(monkeypatch, tmp_path):
    import ctypes

    for name in tdp._DLLS:
        (tmp_path / name).write_bytes(b"stub")

    loaded = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: str(tmp_path))
    monkeypatch.setattr(os, "add_dll_directory", lambda p: None, raising=False)
    monkeypatch.setattr(ctypes, "WinDLL", lambda p: loaded.append(p), raising=False)

    assert tdp.preload_torch_dlls() is True
    assert len(loaded) == len(tdp._DLLS)


def test_add_dll_directory_failure_is_not_fatal(monkeypatch, tmp_path):
    import ctypes

    (tmp_path / tdp._DLLS[0]).write_bytes(b"stub")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tdp, "torch_lib_dir", lambda: str(tmp_path))

    def boom(p):
        raise OSError("no such directory")

    monkeypatch.setattr(os, "add_dll_directory", boom, raising=False)
    monkeypatch.setattr(ctypes, "WinDLL", lambda p: None, raising=False)
    assert tdp.preload_torch_dlls() is True      # still loaded what it could


def test_global_deps_is_loaded_before_c10():
    """Dependency order matters — torch_global_deps pulls in the BLAS/OpenMP
    runtimes that c10 needs."""
    assert tdp._DLLS.index("torch_global_deps.dll") < tdp._DLLS.index("c10.dll")


def test_this_test_module_imports_no_qt_and_no_torch():
    """The guard that keeps this file from re-creating the very problem it
    tests (PyQt5 before torch in the pytest process = WinError 1114 for every
    later torch import, and this file sorts before many of them)."""
    import subprocess
    code = ("import sys; import tests.test_torch_dll_preload as m; "
            "print('PyQt5' in sys.modules, 'torch' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, timeout=120,
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert out.returncode == 0, out.stderr[-1500:]
    assert out.stdout.strip() == "False False", out.stdout


# --------------------------------------------------------------------- #
#  Source-order guard on run_gui.py                                      #
# --------------------------------------------------------------------- #
# The original bug survived because nothing checked the order and a stale
# comment claimed it was fine. A reorder here silently breaks the brain on
# affected installs, with a window that opens and refuses every command —
# the kind of failure a smoke test only catches if someone thinks to boot
# the GUI. Cheap to assert, so assert it.

def _run_gui_source() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "run_gui.py"), encoding="utf-8") as f:
        return f.read()


def test_run_gui_preloads_torch_dlls_before_importing_pyqt5():
    src = _run_gui_source()

    call = src.find("preload_torch_dlls()")
    assert call != -1, "run_gui.py no longer preloads torch's DLLs"

    import re
    m = re.search(r"^\s*(from PyQt5|import PyQt5)", src, re.MULTILINE)
    assert m, "run_gui.py no longer imports PyQt5?"

    assert call < m.start(), (
        "run_gui.py imports PyQt5 before preloading torch's DLLs — that is "
        "the WinError 1114 order; the brain will fail to start on affected "
        "installs (docs §6.15)")


def test_run_gui_skips_the_preload_under_split_brain():
    """In split mode this process never imports torch, so the preload is pure
    cost — and the child, which starts with no Qt, is immune anyway."""
    src = _run_gui_source()
    window = src[src.find("preload_torch_dlls") - 600:src.find("preload_torch_dlls")]
    assert "AERIS_SPLIT_BRAIN" in window, \
        "the preload is no longer gated on split-brain mode"
