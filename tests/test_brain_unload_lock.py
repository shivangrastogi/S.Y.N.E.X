"""Regression: idle-unload must serialize against encodes via ENCODER_LOCK.

The GUI crashed with Windows heap corruption (0xC0000374) because
try_unload_idle() freed the encoder's torch tensors (on the ResourceMonitor
thread) while a chat-gate encode was running on another thread — a
use-after-free. try_unload_idle / _ensure_loaded now take ENCODER_LOCK, so an
in-flight encode blocks the free entirely. This test proves that ordering
without loading any real model (lazy brain + sentinel encoder objects).
"""

from __future__ import annotations

import threading
import time

from core.brain import JarvisBrain
from core.encoder_lock import ENCODER_LOCK


def _idle_loaded_brain():
    b = JarvisBrain(lazy=True)          # no model load
    b._encoder_loaded = True
    b._last_predict_ts = 0.0            # idle "forever"
    b._idle_unload_s = 0.0             # eligible to unload immediately
    b.classifier.encoder = object()    # sentinel — cleared on unload
    b.classifier.nn = object()
    b.classifier.embeddings = object()
    return b


def test_unload_blocks_while_encoder_lock_held():
    b = _idle_loaded_brain()
    done = threading.Event()
    result = {}

    def worker():
        # from ANOTHER thread → ENCODER_LOCK (RLock) will block until released
        result["r"] = b.try_unload_idle()
        done.set()

    with ENCODER_LOCK:                  # simulate an in-flight encode
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        time.sleep(0.3)
        # must NOT have freed the encoder while we hold the lock
        assert not done.is_set(), "try_unload_idle freed encoder mid-encode!"
        assert b.classifier.encoder is not None

    # lock released → the unload may now proceed
    t.join(3)
    assert done.is_set() and result.get("r") is True
    assert b.classifier.encoder is None
    assert b.classifier.nn is None


def test_unload_runs_freely_when_lock_is_free():
    b = _idle_loaded_brain()
    assert b.try_unload_idle() is True      # no contention → unloads
    assert b.classifier.encoder is None


def test_not_idle_does_not_unload():
    b = _idle_loaded_brain()
    b._last_predict_ts = time.monotonic()   # just used
    b._idle_unload_s = 999.0
    assert b.try_unload_idle() is False
    assert b.classifier.encoder is not None  # kept hot
