"""Focused single-gesture practice session — counts hits and reports accuracy.

The user picks one gesture by name (e.g. ``peace``). The practice engine
subscribes to the GestureEngine, counts every fire of that gesture for
the next ``session_seconds`` (default 30), and reports the result.

Public API:
    sess = start_practice(target, session_seconds=30) -> dict (the session)
    status() -> Optional[dict]    # currently-running session, if any
    stop_practice() -> Optional[dict]
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)


_LOCK = threading.RLock()
_SESSION: Optional[dict] = None


def _on_gesture(name: str) -> None:
    with _LOCK:
        if _SESSION is None:
            return
        sess = _SESSION
        if not sess["running"]:
            return
        if name == sess["target"]:
            sess["hits"] += 1
            sess["last_hit_ts"] = time.monotonic()
        else:
            sess["misses"] += 1


def start_practice(target: str, session_seconds: int = 30) -> dict:
    """Begin a practice session. Returns the in-progress session dict
    (callers can poll its 'hits' / 'remaining_s' / 'running' fields)."""
    global _SESSION
    target = (target or "").strip()
    if not target:
        return {"error": "Target gesture name nahi diya."}
    try:
        from core.gesture_engine import get_gesture_engine
        eng = get_gesture_engine()
        # Start if needed so events flow.
        if not eng.is_enabled():
            eng.start()
        eng.add_listener(_on_gesture)
    except Exception as e:
        return {"error": f"GestureEngine unreachable: {e}"}

    with _LOCK:
        sess = {
            "target": target,
            "started_at": time.monotonic(),
            "duration_s": max(5, int(session_seconds)),
            "hits": 0,
            "misses": 0,
            "last_hit_ts": 0.0,
            "running": True,
            "error": None,
        }
        _SESSION = sess
    log.info("[practice] started — target=%s for %ds", target, session_seconds)
    return sess


def status() -> Optional[dict]:
    with _LOCK:
        if _SESSION is None:
            return None
        sess = dict(_SESSION)
    now = time.monotonic()
    elapsed = now - sess["started_at"]
    remaining = max(0, int(sess["duration_s"] - elapsed))
    sess["elapsed_s"] = int(elapsed)
    sess["remaining_s"] = remaining
    if remaining <= 0 and sess["running"]:
        # Time's up — auto-stop on read.
        _finish_session()
        with _LOCK:
            if _SESSION is not None:
                sess["running"] = _SESSION["running"]
                sess["accuracy"] = _SESSION.get("accuracy", 0.0)
    if sess["hits"] + sess["misses"] > 0:
        sess["accuracy"] = round(
            sess["hits"] / (sess["hits"] + sess["misses"]), 2
        )
    else:
        sess["accuracy"] = 0.0
    return sess


def _finish_session() -> None:
    global _SESSION
    with _LOCK:
        if _SESSION is None:
            return
        _SESSION["running"] = False
        total = _SESSION["hits"] + _SESSION["misses"]
        _SESSION["accuracy"] = (round(_SESSION["hits"] / total, 2)
                                if total else 0.0)
    log.info("[practice] finished — hits=%d misses=%d acc=%.2f",
             _SESSION["hits"], _SESSION["misses"], _SESSION["accuracy"])


def stop_practice() -> Optional[dict]:
    """Stop early and return the final session dict."""
    snap = status()
    _finish_session()
    return snap
