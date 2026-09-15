"""One place that makes torch safe to use in this process.

Historically the GUI's BrainWorker did this right after pre-importing torch:

    torch.set_num_threads(1); torch.set_num_interop_threads(1)

Pinning matters — with the duplicate OpenMP runtime this machine runs under
(`KMP_DUPLICATE_LIB_OK=TRUE`), multi-threaded tensor ops have corrupted the
heap (0xC0000374). Now that torch is imported lazily (lite boot / tiered
router), the pin has to happen wherever torch *actually* first loads rather
than at a fixed point in the boot sequence — so every lazy load funnels
through ``pin_torch_threads()``.

Idempotent, thread-safe, and never raises: torch missing or already-started
interop pools just leave the process as it was.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

_lock = threading.Lock()
_done = False


def pin_torch_threads() -> bool:
    """Pin torch to a single compute thread. True if the pin was applied."""
    global _done
    with _lock:
        if _done:
            return False
        _done = True
        try:
            import torch
        except Exception as e:            # torch not installed — nothing to do
            log.debug("[torch_setup] torch unavailable: %s", e)
            return False
        try:
            torch.set_num_threads(1)
        except Exception as e:
            log.debug("[torch_setup] set_num_threads failed: %s", e)
        try:
            # Raises if the interop pool has already been used — harmless.
            torch.set_num_interop_threads(1)
        except Exception as e:
            log.debug("[torch_setup] set_num_interop_threads skipped: %s", e)
        log.info("[torch_setup] torch pinned to 1 compute thread")
        return True
