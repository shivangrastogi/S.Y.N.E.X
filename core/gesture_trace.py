"""Structured gesture-emit logger.

Every gesture decision (emitted OR blocked) is appended to
``data/logs/gesture_trace.log`` as JSON-line records:

    {"ts": "2026-05-24T14:30:00", "gesture": "double_pinch",
     "status": "fired", "faces": ["shivang"], "blocked_reason": null}

Tiny, append-only, no rotation (the log doesn't grow that fast — a few
hundred bytes per gesture). Skills surface the last N lines.

Public API:
  * ``log_fire(gesture)``       — gesture made it through every gate
  * ``log_block(gesture, why)`` — gesture was suppressed
  * ``tail(n=20)``              — return last N parsed records (newest last)
  * ``trace_path()``            — absolute path to the log file
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LOG_PATH = os.path.join(_ROOT, "data", "logs", "gesture_trace.log")
_LOCK = threading.Lock()


def trace_path() -> str:
    return _LOG_PATH


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)


def _append(record: dict) -> None:
    _ensure_dir()
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        try:
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            log.debug("[gesture_trace] write failed: %s", e)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _faces_in_frame() -> list[str]:
    try:
        from core.face_gate import last_identified
        return list(last_identified())
    except Exception:
        return []


def log_fire(gesture: str) -> None:
    _append({
        "ts": _now_iso(),
        "gesture": gesture,
        "status": "fired",
        "faces": _faces_in_frame(),
        "blocked_reason": None,
    })


def log_block(gesture: str, reason: str) -> None:
    _append({
        "ts": _now_iso(),
        "gesture": gesture,
        "status": "blocked",
        "faces": _faces_in_frame(),
        "blocked_reason": reason,
    })


def tail(n: int = 20) -> list[dict]:
    if not os.path.exists(_LOG_PATH):
        return []
    try:
        # Tiny file — fully reading is cheap.
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    out: list[dict] = []
    for ln in lines[-n:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def clear() -> int:
    """Wipe the trace log. Returns the number of bytes removed."""
    if not os.path.exists(_LOG_PATH):
        return 0
    with _LOCK:
        try:
            size = os.path.getsize(_LOG_PATH)
            os.remove(_LOG_PATH)
            return size
        except Exception:
            return 0
