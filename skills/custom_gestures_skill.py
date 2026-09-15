"""User-controllable custom-gesture training.

Skills:
  * ``gesture_record <name>``     — start recording a new gesture (default 12 frames)
  * ``gesture_unteach <name>``    — drop a recorded gesture
  * ``gesture_list_custom``       — list saved custom gestures
  * ``gesture_record_status``     — recording progress / "not recording"

The actual landmark capture happens via the gesture engine's per-frame
loop (see core/custom_gestures.feed). This skill module is just the
voice surface.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _extract_name(text: str, *triggers: str) -> str:
    if not text:
        return ""
    s = text.strip()
    sl = s.lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if sl.startswith(trig):
            return s[len(trig):].strip(" .,?\"'")
    return ""


# ── gesture_record ─────────────────────────────────────────────────


@skill(
    name="gesture_record",
    description="Record a new custom gesture under a name — hold the pose "
                "until AERIS confirms it's saved.",
    patterns=[
        "record gesture", "record new gesture",
        "teach new gesture", "teach gesture",
        "new gesture", "custom gesture",
        "save this gesture", "gesture record karo",
        "naya gesture sikhao", "gesture sikhao",
        "record custom gesture",
    ],
    required_entities=[],
)
def gesture_record(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name(
        text,
        "record new custom gesture", "record custom gesture",
        "record new gesture",
        "teach new gesture as", "teach gesture as",
        "save this gesture as",
        "record gesture as", "record gesture",
        "teach new gesture", "teach gesture",
        "save this gesture", "new gesture",
        "custom gesture", "naya gesture sikhao",
        "gesture sikhao", "gesture record karo",
    )
    if not name:
        return ("Naam batao — e.g. 'record gesture as my-pose'.")
    try:
        from core.custom_gestures import get_custom_gesture_engine
    except Exception as e:
        return f"custom_gestures load fail: {e}"
    eng = get_custom_gesture_engine()
    ok, msg = eng.start_recording(name)
    return msg


# ── gesture_unteach ────────────────────────────────────────────────


@skill(
    name="gesture_unteach",
    description="Forget a previously-trained custom gesture.",
    patterns=[
        "unteach gesture", "forget gesture", "remove custom gesture",
        "delete gesture", "delete custom gesture",
        "gesture hatao", "gesture bhul jao",
        "unteach custom gesture",
    ],
    required_entities=[],
)
def gesture_unteach(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name(
        text,
        "unteach custom gesture", "remove custom gesture",
        "delete custom gesture",
        "unteach gesture", "forget gesture",
        "delete gesture", "gesture hatao", "gesture bhul jao",
    )
    if not name:
        return "Kis gesture ko forget karna hai?"
    try:
        from core.custom_gestures import get_custom_gesture_engine
    except Exception as e:
        return f"custom_gestures load fail: {e}"
    if get_custom_gesture_engine().forget(name.lower()):
        return f"Forgot '{name}'."
    return f"'{name}' custom gesture nahi tha."


# ── gesture_list_custom ────────────────────────────────────────────


@skill(
    name="gesture_list_custom",
    description="List all trained custom gestures.",
    patterns=[
        "list custom gestures", "custom gestures dikhao",
        "show custom gestures", "saved gestures",
        "kaunse custom gestures hain", "my gestures",
        "list my gestures",
    ],
    required_entities=[],
)
def gesture_list_custom(_slots: dict) -> str:
    try:
        from core.custom_gestures import get_custom_gesture_engine
    except Exception as e:
        return f"custom_gestures load fail: {e}"
    names = get_custom_gesture_engine().list_names()
    if not names:
        return "Koi custom gesture record nahi kiya hai."
    return f"{len(names)} custom gesture(s): " + ", ".join(names)


# ── gesture_record_status ──────────────────────────────────────────


@skill(
    name="gesture_record_status",
    description="Report whether a custom-gesture recording is in progress.",
    patterns=[
        "gesture record status", "gesture recording status",
        "recording status gesture", "kya gesture record ho raha hai",
    ],
    required_entities=[],
)
def gesture_record_status(_slots: dict) -> str:
    try:
        from core.custom_gestures import get_custom_gesture_engine
    except Exception as e:
        return f"custom_gestures load fail: {e}"
    eng = get_custom_gesture_engine()
    if not eng.is_recording():
        return "Koi gesture recording chal raha nahi."
    name, n, target = eng.recording_progress()
    return f"Recording '{name}': {n}/{target} samples — keep holding the pose."
