"""Voice-fingerprint speaker identification — voice command surface.

Backed by ``core.voice_id`` (scipy-only spectral envelope, best-effort).
For production-grade accuracy, install ``resemblyzer`` and a future
iteration can swap the backend transparently.

Skills:
  * ``speaker_enroll <name>``  — record 4 s of your voice + store signature
  * ``speaker_identify``       — record 2 s, return best match
  * ``speaker_list``           — list enrolled names
  * ``speaker_forget <name>``  — drop an enrollment
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
    t = text.strip()
    tl = t.lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if tl.startswith(trig):
            return t[len(trig):].strip(" .,?\"'")
    return ""


# ── speaker_enroll ─────────────────────────────────────────────────


@skill(
    name="speaker_enroll",
    description="Record 4 seconds of your voice and store a speaker signature "
                "for future identification.",
    patterns=[
        "enroll my voice", "speaker enroll",
        "register my voice", "enroll voice as",
        "register voice as", "voice enroll karo",
        "meri voice register karo", "voice identify train",
        "speaker enroll as", "voice fingerprint",
    ],
    required_entities=[],
)
def speaker_enroll(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name(
        text,
        "enroll my voice as", "register my voice as",
        "enroll voice as", "register voice as",
        "speaker enroll as",
        "voice enroll karo as", "meri voice register karo as",
        "enroll my voice", "register my voice",
        "enroll voice", "register voice",
        "speaker enroll", "voice enroll karo",
        "meri voice register karo",
        "voice fingerprint",
    )
    if not name:
        return "Naam bata — e.g. 'enroll my voice as shivang'."
    try:
        from core.voice_id import get_voice_id_engine
    except Exception as e:
        return f"voice_id module load fail: {e}"
    eng = get_voice_id_engine()
    if not eng.is_available():
        return ("Voice ID backend unavailable — numpy/pyaudio missing. "
                "For better accuracy install 'resemblyzer'.")
    ok, msg = eng.enroll(name)
    return msg


# ── speaker_identify ───────────────────────────────────────────────


@skill(
    name="speaker_identify",
    description="Listen for 2 s and identify the loudest enrolled speaker.",
    patterns=[
        "identify speaker", "who's speaking", "kaun bol raha hai",
        "identify voice", "voice identify karo",
        "speaker identify",
        "recognise voice", "recognize voice",
        "voice pehchaano", "kis ki voice hai",
    ],
    required_entities=[],
)
def speaker_identify(_slots: dict) -> str:
    try:
        from core.voice_id import get_voice_id_engine
    except Exception as e:
        return f"voice_id module load fail: {e}"
    eng = get_voice_id_engine()
    if not eng.is_available():
        return "Voice ID backend unavailable."
    if not eng.list_speakers():
        return "Koi speaker enrolled nahi — pehle 'enroll my voice as <name>' bolo."
    name, sim = eng.identify()
    if name is None:
        return f"Pehchana nahi (best similarity {sim:.2f})."
    return f"Identified: {name} (similarity {sim:.2f})."


# ── speaker_list ───────────────────────────────────────────────────


@skill(
    name="speaker_list",
    description="List every enrolled speaker.",
    patterns=[
        "list speakers", "show speakers", "speakers dikhao",
        "kaun kaun enrolled hai", "speaker list",
        "voice id list", "list enrolled voices",
    ],
    required_entities=[],
)
def speaker_list(_slots: dict) -> str:
    try:
        from core.voice_id import get_voice_id_engine
    except Exception as e:
        return f"voice_id load fail: {e}"
    names = get_voice_id_engine().list_speakers()
    if not names:
        return "Koi speaker enrolled nahi."
    return f"{len(names)} enrolled: " + ", ".join(names)


# ── speaker_forget ─────────────────────────────────────────────────


@skill(
    name="speaker_forget",
    description="Remove an enrolled speaker from the voice-ID registry.",
    patterns=[
        "forget speaker", "speaker forget", "delete speaker",
        "remove speaker", "voice id se hatao",
    ],
    required_entities=[],
)
def speaker_forget(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name(
        text,
        "forget speaker", "speaker forget",
        "delete speaker", "remove speaker",
        "voice id se hatao",
    )
    if not name:
        return "Kis speaker ko forget karna hai?"
    try:
        from core.voice_id import get_voice_id_engine
    except Exception as e:
        return f"voice_id load fail: {e}"
    if get_voice_id_engine().forget(name.lower()):
        return f"Forgot '{name}'."
    return f"'{name}' enrolled nahi tha."
