"""Voice control for the auto-label engine.

When ON, AERIS narrates objects that come close to the camera. Useful
for "show this to the camera and tell me what it is" workflows.

Skills:
  * ``auto_label_on``  — start engine + return active state
  * ``auto_label_off`` — stop engine
  * ``auto_label_status`` — query current state + last seen labels
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_LAST_SEEN: list[tuple[float, str, float]] = []   # (ts, label, score)
_MAX_HISTORY = 8

_SPEAK_ENABLED = False
_LAST_SPOKEN_AT: dict[str, float] = {}    # label → ts of last spoken
_SPEAK_COOLDOWN_S = 8.0                   # don't repeat same label too often


def _record(label: str, score: float, _bbox) -> None:
    _LAST_SEEN.append((time.monotonic(), label, score))
    if len(_LAST_SEEN) > _MAX_HISTORY:
        del _LAST_SEEN[: len(_LAST_SEEN) - _MAX_HISTORY]
    log.info("[auto_label] saw %s (%.2f)", label, score)
    if _SPEAK_ENABLED:
        _maybe_speak(label, score)


def _maybe_speak(label: str, score: float) -> None:
    """Speak the label via TTS when it's a fresh-ish object."""
    now = time.monotonic()
    last = _LAST_SPOKEN_AT.get(label, 0.0)
    if (now - last) < _SPEAK_COOLDOWN_S:
        return
    _LAST_SPOKEN_AT[label] = now
    # Pretty up COCO labels — "cell phone" → "cell phone" (already fine),
    # but underscores / dashes get stripped for spoken output.
    spoken = label.replace("_", " ").replace("-", " ").strip()
    msg = f"I see a {spoken}."
    try:
        # Run TTS in a daemon thread so blocking speak() doesn't stall
        # the auto-label fan-out (which runs on the camera thread).
        import threading
        threading.Thread(target=_speak_blocking, args=(msg,),
                         daemon=True).start()
    except Exception as e:
        log.debug("[auto_label_skill] speak dispatch failed: %s", e)


def _speak_blocking(msg: str) -> None:
    try:
        from core.tts import TTS
        TTS().speak(msg)
    except Exception as e:
        log.info("[auto_label_skill] tts speak failed: %s", e)


def _ensure_listener_registered():
    """Idempotently attach _record as a listener on the singleton."""
    try:
        from core.auto_label import get_auto_label_engine
        eng = get_auto_label_engine()
        # Cheap dedup: check the listener list directly.
        with eng._lock:
            for fn in eng._listeners:
                if fn is _record:
                    return eng
            eng._listeners.append(_record)
        return eng
    except Exception as e:
        log.info("[auto_label_skill] listener wire failed: %s", e)
        return None


# ── auto_label_on ──────────────────────────────────────────────────


@skill(
    name="auto_label_on",
    description="Start auto object labeling — narrate items held up to the camera.",
    patterns=[
        "auto label on", "object label on", "start labeling",
        "label objects", "labels on", "auto labeling chalu karo",
        "narrate objects", "objects identify karo",
        "vision describe on", "label mode on",
    ],
    required_entities=[],
)
def auto_label_on(_slots: dict) -> str:
    eng = _ensure_listener_registered()
    if eng is None:
        return ("Auto-label engine load nahi hua — opencv-python + ultralytics check karo.")
    if eng.is_enabled():
        return "Auto-label already ON hai."
    if eng.start():
        return ("Auto-label ON. Camera ke saamne kuch lao — main label bol dunga. "
                "'auto label off' to band karne ke liye.")
    return ("Auto-label start fail — camera available hai? "
            "'diagnose' chalao to check karo.")


# ── auto_label_off ─────────────────────────────────────────────────


@skill(
    name="auto_label_off",
    description="Stop auto object labeling.",
    patterns=[
        "auto label off", "object label off", "stop labeling",
        "labels off", "auto labeling band karo",
        "stop narrating", "label mode off",
        "objects mat batao", "vision describe off",
    ],
    required_entities=[],
)
def auto_label_off(_slots: dict) -> str:
    try:
        from core.auto_label import get_auto_label_engine
    except Exception as e:
        return f"auto_label load fail: {e}"
    eng = get_auto_label_engine()
    if not eng.is_enabled():
        return "Auto-label already OFF tha."
    eng.stop()
    return "Auto-label OFF."


# ── auto_label_status ──────────────────────────────────────────────


@skill(
    name="auto_label_status",
    description="Report whether auto-labeling is running and what was seen recently.",
    patterns=[
        "auto label status", "labels status", "what did you see",
        "kya kya dekha", "recent objects", "last seen objects",
        "auto labeling status",
    ],
    required_entities=[],
)
def auto_label_status(_slots: dict) -> str:
    try:
        from core.auto_label import get_auto_label_engine
    except Exception as e:
        return f"auto_label load fail: {e}"
    eng = get_auto_label_engine()
    state = "ON" if eng.is_enabled() else "OFF"
    speak = "ON" if _SPEAK_ENABLED else "OFF"
    if not _LAST_SEEN:
        return f"Auto-label: {state} (speak: {speak}). Abhi tak kuch label nahi hua."
    now = time.monotonic()
    recent = [(label, score, now - ts) for ts, label, score in _LAST_SEEN[-5:]]
    lines = [f"Auto-label: {state} (speak: {speak}). Last {len(recent)} seen:"]
    for label, score, ago in recent:
        lines.append(f"  • {label}  ({score:.2f})  {ago:.1f}s ago")
    return "\n".join(lines)


# ── auto_label_speak_on / off ──────────────────────────────────────


@skill(
    name="auto_label_speak_on",
    description="Make auto-label speak each new object's name out loud.",
    patterns=[
        "speak labels", "narrate labels on", "speak objects",
        "objects bolo", "label bolna chalu karo",
        "label speech on", "narrate what you see",
    ],
    required_entities=[],
)
def auto_label_speak_on(_slots: dict) -> str:
    global _SPEAK_ENABLED
    _SPEAK_ENABLED = True
    return ("Auto-label speech ON. Naye objects ko awaaz se bata dunga "
            f"(per-label cooldown {int(_SPEAK_COOLDOWN_S)}s).")


@skill(
    name="auto_label_speak_off",
    description="Stop speaking auto-label results (chat/log entries continue).",
    patterns=[
        "stop speaking labels", "narrate labels off", "labels mat bolo",
        "object speech off", "label speech off",
    ],
    required_entities=[],
)
def auto_label_speak_off(_slots: dict) -> str:
    global _SPEAK_ENABLED
    _SPEAK_ENABLED = False
    return "Auto-label speech OFF. Chat me labels dikhte rahenge."
