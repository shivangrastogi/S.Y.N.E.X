"""Master-user face gate for the GestureEngine.

The GestureEngine consults ``is_master_present()`` before firing any
gesture. When the user has configured a non-empty ``master_users`` list
in settings, only frames where one of those identified faces is present
will trigger gestures. Strangers can wave at the screen all day without
triggering anything.

Throttling: face detection runs at most every ``_FACE_INTERVAL_S`` (default
0.7 s). Between runs the last-known answer is reused so the gesture loop
isn't blocked on InsightFace inference.

Settings keys:
  * ``master_users`` — list[str] of names (case-insensitive). When empty,
    the gate is OPEN (every frame passes) — backward compatible.
  * ``master_gate_strict`` — bool. When True AND no face is detected at
    all (camera covered / user away), gestures still fire. When False
    (default), no-face frames also pass. Set True for kid-proofing.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)


_FACE_INTERVAL_S = 0.7      # min seconds between face inferences
_NEGATIVE_GRACE_S = 2.5     # if a master was just seen, treat next few frames as OK
                            # (smooths over brief detection misses)


class _GateState:
    __slots__ = ("last_inference_at", "last_names", "last_master_seen_at",
                 "settings_cache_at", "masters_cache", "strict_cache",
                 "blocks_total", "blocks_last_minute", "blocks_minute_start",
                 "lock")

    def __init__(self):
        self.last_inference_at: float = 0.0
        self.last_names: list[Optional[str]] = []
        self.last_master_seen_at: float = 0.0
        self.settings_cache_at: float = 0.0
        self.masters_cache: list[str] = []
        self.strict_cache: bool = False
        # ── observability ──
        self.blocks_total: int = 0
        self.blocks_last_minute: int = 0
        self.blocks_minute_start: float = 0.0
        self.lock = threading.RLock()


_STATE = _GateState()


def record_block(gesture_name: str = "") -> int:
    """Count a gesture that was suppressed by the gate. Returns the total
    blocks seen this minute (callers can use it to throttle toasts).
    Fires a Win10 toast on the FIRST block per minute so the user knows
    why nothing happened.
    """
    now = time.monotonic()
    with _STATE.lock:
        _STATE.blocks_total += 1
        first_of_minute = (now - _STATE.blocks_minute_start) >= 60.0
        if first_of_minute:
            _STATE.blocks_minute_start = now
            _STATE.blocks_last_minute = 1
        else:
            _STATE.blocks_last_minute += 1
        in_minute = _STATE.blocks_last_minute

    if first_of_minute:
        _toast_stranger_block(gesture_name)
    return in_minute


def _toast_stranger_block(gesture_name: str) -> None:
    """Best-effort Win10 toast on the first stranger-block per minute.
    Silent fallback when win10toast is missing or fires on a worker thread."""
    try:
        # Run on a daemon thread so the camera-callback chain isn't blocked
        # by the toast UI (win10toast spawns its own message-pump).
        import threading
        threading.Thread(
            target=_toast_blocking,
            args=(gesture_name,),
            daemon=True,
        ).start()
    except Exception as e:
        log.debug("[face_gate] toast dispatch failed: %s", e)


def _toast_blocking(gesture_name: str) -> None:
    try:
        from win10toast import ToastNotifier  # type: ignore
        title = "AERIS — gesture suppressed"
        body = (f"Stranger or unrecognised face — '{gesture_name or 'gesture'}' "
                f"was blocked. Say 'face gate status' to inspect.")
        ToastNotifier().show_toast(title, body, duration=4, threaded=True)
    except Exception as e:
        log.info("[face_gate] win10toast unavailable: %s", e)


def block_stats() -> dict:
    """Snapshot of the block counters for the diagnostics surface."""
    with _STATE.lock:
        return {
            "total": _STATE.blocks_total,
            "last_minute": _STATE.blocks_last_minute,
            "minute_window_s": max(0.0, time.monotonic() - _STATE.blocks_minute_start)
                              if _STATE.blocks_minute_start else 0.0,
        }


def last_identified() -> list[str]:
    """Names currently believed to be in front of the camera. Empty when
    no recent inference. Used by the gesture-trace log."""
    with _STATE.lock:
        return [n for n in _STATE.last_names if n]


def _refresh_settings(now: float) -> tuple[list[str], bool]:
    """Re-read master_users / strict from settings every 2 s."""
    if now - _STATE.settings_cache_at < 2.0:
        return _STATE.masters_cache, _STATE.strict_cache
    try:
        from core import settings as _settings
        masters = _settings.get("master_users") or []
        if not isinstance(masters, list):
            masters = []
        # Normalise: lowercase, no whitespace-only.
        masters = [str(m).strip().lower() for m in masters if str(m).strip()]
        strict = bool(_settings.get("master_gate_strict", False))
    except Exception:
        masters, strict = [], False
    _STATE.masters_cache = masters
    _STATE.strict_cache = strict
    _STATE.settings_cache_at = now
    return masters, strict


def gesture_allowed_for(face_names: list[str], gesture: str) -> bool:
    """Return True when at least one face in ``face_names`` is allowed to
    fire ``gesture`` per the ``master_permissions`` settings map.

    ``master_permissions`` shape (settings.json):
        {
          "shivang": ["all"],
          "kid":     ["double_pinch", "swipe_left", "swipe_right"]
        }

    Defaults:
      * unspecified user OR ``["all"]`` → every gesture
      * empty list                       → no gestures (read-only kid mode)
      * named list                       → only those gestures
    """
    try:
        from core import settings as _settings
        perms = _settings.get("master_permissions") or {}
    except Exception:
        perms = {}
    if not isinstance(perms, dict) or not perms:
        return True   # no permission map → backward-compatible: allow all
    for name in face_names:
        nl = (name or "").strip().lower()
        if nl not in perms:
            # Unknown master in the map → fall through to next face.
            continue
        allowed = perms[nl]
        if not isinstance(allowed, list):
            allowed = []
        if not allowed:
            continue          # explicitly empty list = denied for this user
        if "all" in allowed or "*" in allowed or gesture in allowed:
            return True
    # No face in the list has permission for this gesture.
    return False


def is_master_present(frame_bgr=None) -> bool:
    """Return True when a master user is in frame (or gating is disabled).

    Pass a current ``frame_bgr`` to allow on-demand face inference. When
    the throttle says we're inside the cool-down, the cached answer is
    reused without running InsightFace.
    """
    now = time.monotonic()
    masters, strict = _refresh_settings(now)

    # No master list configured → gate is OPEN.
    if not masters:
        return True

    # Hot path: re-use cache when inside throttle window.
    with _STATE.lock:
        if (now - _STATE.last_inference_at) < _FACE_INTERVAL_S:
            return _decide(masters, strict, _STATE.last_names, now)

    # Cold path: need a fresh inference. Skip when no frame supplied.
    if frame_bgr is None:
        with _STATE.lock:
            return _decide(masters, strict, _STATE.last_names, now)

    try:
        from core.face_recognition import get_recognizer
        rec = get_recognizer()
        if not rec.is_available():
            # Recogniser unavailable → fail open (would otherwise lock
            # the user out of their own assistant).
            return True
        names = rec.identify_faces(frame_bgr)
    except Exception as e:
        log.debug("[face_gate] identify failed: %s", e)
        return True

    with _STATE.lock:
        _STATE.last_names = [(n or "").lower() if n else None for n in names]
        _STATE.last_inference_at = now
        if _any_master(_STATE.last_names, masters):
            _STATE.last_master_seen_at = now
        return _decide(masters, strict, _STATE.last_names, now)


def _any_master(names: list[Optional[str]], masters: list[str]) -> bool:
    for n in names:
        if n and n in masters:
            return True
    return False


def _decide(masters: list[str], strict: bool,
            names: list[Optional[str]], now: float) -> bool:
    # If a master was seen very recently, treat the next few frames as OK
    # so a momentary detection miss doesn't break the gesture mid-flow.
    if (now - _STATE.last_master_seen_at) < _NEGATIVE_GRACE_S:
        return True
    if not names:
        # No face detected. Strict gate: deny. Lax gate (default): allow.
        return not strict
    return _any_master(names, masters)


def explain() -> str:
    """One-line summary for the diagnostics skill."""
    now = time.monotonic()
    masters, strict = _refresh_settings(now)
    stats = block_stats()
    block_tail = (f" · blocked {stats['total']} gesture(s) total "
                  f"({stats['last_minute']} in last minute)") if stats["total"] else ""
    if not masters:
        return "Face gate: DISABLED (no master_users set) — every face allowed." + block_tail
    last_seen = (now - _STATE.last_master_seen_at) if _STATE.last_master_seen_at else None
    seen_str = f"last master seen {last_seen:.1f}s ago" if last_seen is not None else "never seen"
    mode = "strict" if strict else "lax"
    return (f"Face gate: ENABLED — {len(masters)} master(s) "
            f"({', '.join(masters)}), {mode} mode, {seen_str}." + block_tail)
