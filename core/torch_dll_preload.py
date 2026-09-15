"""Make torch loadable after Qt on Windows, without paying for torch at boot.

The problem
-----------
On Windows, once Qt's CRT DLLs are resident, some torch builds can no longer
initialise theirs:

    OSError: [WinError 1114] A dynamic link library (DLL) initialization
    routine failed. Error loading ...\\torch\\lib\\c10.dll

AERIS's instant-boot path imports PyQt5 first and lets `BrainWorker` import
torch later on its own thread — which is precisely the order that fails. On
this machine (py3.10 + torch 2.10.0+cpu) the window opens and then never
accepts a command, because the brain dies on `import torch`.

Measured, three ways:

===========================================  ==================================
order                                        result
===========================================  ==================================
PyQt5 -> QApplication -> torch (worker)      WinError 1114
torch -> PyQt5 -> QApplication               works (torch import costs ~1.6 s)
**this module** -> PyQt5 -> torch (worker)   works, costs ~0.2 s
===========================================  ==================================

The trick is that torch's DLLs only need to be *loaded* before Qt's, not the
Python package imported. Loading the three native libraries with `ctypes`
takes ~0.2 s against ~1.6 s for a full `import torch`, so instant boot keeps
its fast first paint and the brain still comes up.

**Order is everything.** Running this *after* `QApplication` exists does not
help — `c10.dll` then fails with 1114 on the ctypes load too (measured). Call
it from the process entry point, before PyQt5 is imported. There is no useful
place for it inside `BrainWorker`.

Skip it entirely when the brain runs in a child process
(`AERIS_SPLIT_BRAIN=1`): the GUI never imports torch at all there, so the
child — which starts clean, with no Qt — is immune by construction.

Silent and best-effort: a missing file, a renamed DLL in a future torch, a
non-Windows platform, all just mean "did nothing". The worst case is the
behaviour we already have.
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)

# Loaded in dependency order. torch_global_deps pulls in the BLAS/OpenMP
# runtimes; c10 is the one that actually reports 1114 when Qt got there first.
_DLLS = ("torch_global_deps.dll", "c10.dll", "torch_cpu.dll")

_done = False


def torch_lib_dir() -> str | None:
    """Locate ``torch/lib`` WITHOUT importing torch (that is the whole point).

    ``find_spec`` resolves the package location without executing its
    ``__init__``, so this stays cheap and does not trip the very DLL load we
    are trying to sequence.
    """
    try:
        import importlib.util
        spec = importlib.util.find_spec("torch")
    except Exception as e:
        log.debug("[torch_dll] find_spec failed: %s", e)
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    for base in spec.submodule_search_locations:
        lib = os.path.join(base, "lib")
        if os.path.isdir(lib):
            return lib
    return None


def preload_torch_dlls() -> bool:
    """Load torch's native libraries early. True if anything was loaded.

    Call BEFORE importing PyQt5. Idempotent; never raises.
    """
    global _done
    if _done or sys.platform != "win32":
        return False
    _done = True

    lib = torch_lib_dir()
    if not lib:
        log.debug("[torch_dll] torch not installed — nothing to preload")
        return False

    import ctypes
    try:
        os.add_dll_directory(lib)
    except Exception as e:
        log.debug("[torch_dll] add_dll_directory(%s) failed: %s", lib, e)

    loaded = []
    for name in _DLLS:
        path = os.path.join(lib, name)
        if not os.path.exists(path):
            continue                      # torch layout changed — fine
        try:
            ctypes.WinDLL(path)
            loaded.append(name)
        except Exception as e:
            # Most likely we were called too late (Qt already up). Nothing to
            # do but let BrainWorker's own import report the real error.
            log.debug("[torch_dll] %s did not load: %s", name, e)

    if loaded:
        log.info("[torch_dll] preloaded %s from %s", ", ".join(loaded), lib)
    return bool(loaded)
