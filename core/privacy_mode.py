"""Privacy mode — hard 'stop listening' state.

When ON:
  * VoiceEngine / wake-word stops
  * GestureEngine stops (releases camera too)
  * AutoLabelEngine + PresenceEngine stop
  * The state is persisted in settings so it survives restart

When OFF:
  * Subsystems are NOT auto-resumed (the user explicitly enabled them
    before entering privacy mode, so we let them decide what to bring
    back). The skill returns guidance on what to re-enable.

Public API:
    enable()  -> list[str]   # names of stopped subsystems
    disable() -> str
    is_on()   -> bool
    explain() -> str         # human-readable status line
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)


_PRIVACY_KEY = "privacy_mode"


def _settings_get(key: str, default=None):
    try:
        from core import settings as _settings
        return _settings.get(key, default)
    except Exception:
        return default


def _settings_set(key: str, value) -> None:
    try:
        from core import settings as _settings
        _settings.set_(key, value)
    except Exception:
        pass


def is_on() -> bool:
    return bool(_settings_get(_PRIVACY_KEY, False))


def _safe_stop(label: str, stopper: Callable[[], None]) -> Optional[str]:
    try:
        stopper()
        return label
    except Exception as e:
        log.debug("[privacy] %s stop failed: %s", label, e)
        return None


def enable() -> list[str]:
    """Stop every listener subsystem. Returns the labels of subsystems
    actually stopped (so the skill can surface a clean summary)."""
    stopped: list[str] = []

    # Gesture engine — also releases camera via VisionEngine auto-stop.
    try:
        from core.gesture_engine import get_gesture_engine
        ge = get_gesture_engine()
        if ge.is_enabled():
            r = _safe_stop("gestures", ge.stop)
            if r: stopped.append(r)
    except Exception:
        pass

    # Cursor mode subset of gesture engine — defensive switch-off.
    try:
        from core.gesture_engine import get_gesture_engine
        if get_gesture_engine().is_cursor_mode():
            get_gesture_engine().set_cursor_mode(False)
            stopped.append("cursor-mode")
    except Exception:
        pass

    # Auto-label engine.
    try:
        from core.auto_label import get_auto_label_engine
        al = get_auto_label_engine()
        if al.is_enabled():
            r = _safe_stop("auto-label", al.stop)
            if r: stopped.append(r)
    except Exception:
        pass

    # Presence engine.
    try:
        from core.presence import get_presence_engine
        pe = get_presence_engine()
        if pe.is_enabled():
            r = _safe_stop("presence", pe.stop)
            if r: stopped.append(r)
    except Exception:
        pass

    # Voice engine — wake-word + STT loops.
    try:
        from core.voice_engine import get_voice_engine
        ve = get_voice_engine()
        # voice_engine API varies — try common stop names.
        if hasattr(ve, "stop") and callable(getattr(ve, "stop")):
            r = _safe_stop("voice", ve.stop)
            if r: stopped.append(r)
    except Exception:
        pass

    # Notification mirror.
    try:
        from core.notify_listener import get_listener
        nl = get_listener()
        if nl.is_running():
            r = _safe_stop("notification-mirror", nl.stop)
            if r: stopped.append(r)
    except Exception:
        pass

    _settings_set(_PRIVACY_KEY, True)
    log.info("[privacy] enabled — stopped %s", stopped)
    return stopped


def disable() -> str:
    """Just flip the persisted flag; user re-enables the subsystems they
    want manually so privacy mode can't surprise-restart a camera."""
    _settings_set(_PRIVACY_KEY, False)
    log.info("[privacy] disabled — subsystems remain off until re-enabled.")
    return ("Privacy mode OFF. Subsystems abhi bhi band hain — "
            "manually re-enable kya chahiye: 'gesture mode on', "
            "'auto label on', 'presence auto pause on', etc.")


def explain() -> str:
    state = "ON" if is_on() else "OFF"
    bits = [f"Privacy mode: {state}"]
    try:
        from core.gesture_engine import get_gesture_engine
        bits.append(f"gestures={get_gesture_engine().is_enabled()}")
    except Exception:
        pass
    try:
        from core.auto_label import get_auto_label_engine
        bits.append(f"auto-label={get_auto_label_engine().is_enabled()}")
    except Exception:
        pass
    try:
        from core.presence import get_presence_engine
        bits.append(f"presence={get_presence_engine().is_enabled()}")
    except Exception:
        pass
    try:
        from core.notify_listener import get_listener
        bits.append(f"notif-mirror={get_listener().is_running()}")
    except Exception:
        pass
    return " · ".join(bits)
