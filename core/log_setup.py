"""Root logging configuration for AERIS.

Wraps stdlib ``logging`` with two production-friendly behaviours:

  1. **Rotating file sink** at ``data/logs/aeris.log`` — 10 MB cap × 5
     backups (50 MB total). The rotation is handled by the standard
     library's ``RotatingFileHandler`` which renames atomically.

  2. **One JSON line per structured event** via ``event()``. Goes to the
     SAME rotating file so the entire log stream stays in one place —
     ``grep '"event":"skill_dispatch"'`` filters all dispatch records.

The console handler stays at WARNING so the GUI's logs panel and stderr
aren't noisy; the file handler captures INFO so we have a paper trail
for debugging without spamming the terminal.

Why not structlog?
------------------
structlog is great but adds a dependency. AERIS ships zero-config — a
thin wrapper around stdlib is enough for the property we care about
(one-line-per-event JSON for /metrics consumers).
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
import time
from typing import Any, Callable

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_DIR = os.path.join(_ROOT, "data", "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "aeris.log")

_FILE_BYTES = 10 * 1024 * 1024
_FILE_BACKUPS = 5

_configured = False
_configure_lock = threading.Lock()


def configure(*,
              console_level: int = logging.WARNING,
              file_level: int = logging.INFO,
              fmt: str = "%(asctime)s %(levelname)-5s %(name)s :: %(message)s"
              ) -> None:
    """Set up root logger handlers. Idempotent."""
    global _configured
    with _configure_lock:
        if _configured:
            return
        _configured = True

    os.makedirs(_LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    # Don't blow away existing handlers (e.g. pytest's caplog) — just add
    # ours and let the root level dominate.
    root.setLevel(min(console_level, file_level))

    fmt_obj = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    # Console handler — only attach one if we don't already have one
    # routed to stderr, so re-imports don't multiply output.
    if not any(isinstance(h, logging.StreamHandler)
               and getattr(h, "stream", None) in (sys.stderr, sys.stdout)
               for h in root.handlers):
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(console_level)
        ch.setFormatter(fmt_obj)
        root.addHandler(ch)

    # File handler — rotating, atomic renames.
    fh = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=_FILE_BYTES,
        backupCount=_FILE_BACKUPS, encoding="utf-8",
    )
    fh.setLevel(file_level)
    fh.setFormatter(fmt_obj)
    root.addHandler(fh)

    logging.getLogger(__name__).info(
        "[log_setup] writing to %s (max %d MB × %d backups)",
        _LOG_PATH, _FILE_BYTES // (1024 * 1024), _FILE_BACKUPS,
    )


# ── Structured events ──────────────────────────────────────────────── #

_event_logger = logging.getLogger("aeris.event")

# In-memory ring buffer + subscriber list so the GUI's NotificationsPanel
# (and any future /events endpoint) can observe events without reading
# the rotating log file. Keep the buffer cheap: 500 latest, plain dicts.
from collections import deque as _deque

_EVENT_BUFFER: _deque = _deque(maxlen=500)
_EVENT_SUBS: list = []
_EVENT_LOCK = threading.Lock()


def event(name: str, **fields: Any) -> None:
    """Log one JSON line describing a discrete event.

    Three sinks:
      1. The rotating file via the ``aeris.event`` logger.
      2. The in-memory ring buffer (last 500 events).
      3. Every registered subscriber callable, fired synchronously.

    Subscribers run on the caller's thread — keep them cheap and
    thread-safe (Qt widgets should connect via a queued signal).
    """
    payload = {"ts": time.time(), "event": name}
    payload.update(fields)
    try:
        _event_logger.info(json.dumps(payload, default=str, ensure_ascii=False))
    except Exception:
        _event_logger.info("event=%s (json encode failed)", name)
    # Buffer + fan-out, outside any try/except for the logger so a busted
    # logger doesn't suppress the in-memory notification path.
    with _EVENT_LOCK:
        _EVENT_BUFFER.append(payload)
        subs = list(_EVENT_SUBS)
    for cb in subs:
        try:
            cb(payload)
        except Exception:
            # A bad subscriber must not break event() for everyone else.
            pass


def subscribe_events(cb) -> "Callable[[], None]":
    """Register ``cb(payload_dict)`` for every event. Returns an
    unsubscriber closure. Safe to call from any thread.
    """
    with _EVENT_LOCK:
        _EVENT_SUBS.append(cb)
    def _off():
        with _EVENT_LOCK:
            try: _EVENT_SUBS.remove(cb)
            except ValueError: pass
    return _off


def snapshot_events() -> list[dict]:
    """Cheap copy of the ring buffer — newest LAST. Used by the GUI on
    first-paint to backfill the panel with whatever already happened.
    """
    with _EVENT_LOCK:
        return list(_EVENT_BUFFER)


if __name__ == "__main__":
    configure()
    log = logging.getLogger("smoke")
    log.warning("a regular warning")
    log.info("a regular info — file only")
    event("smoke_test", caller="__main__", n=42, ok=True)
    print(f"check the file at: {_LOG_PATH}")
