"""Voice command surface for the Whisper STT backend.

Skills:
  * ``whisper_status``           — availability + model size
  * ``whisper_transcribe_once``  — capture ~4 s of mic and print the transcript
  * ``whisper_set_model <size>`` — tiny / base / small / medium / large-v3
  * ``stt_prefer_whisper``       — persist a settings flag voice_engine reads
  * ``stt_prefer_google``        — opposite
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)


_WHISPER_PREFERRED_KEY = "stt_backend_preference"   # "whisper" | "google"


@skill(
    name="whisper_status",
    description="Report Whisper STT availability and current model size.",
    patterns=[
        "whisper status", "is whisper available", "whisper stt status",
        "whisper kya hai", "stt status",
    ],
    required_entities=[],
)
def whisper_status(_slots: dict) -> str:
    try:
        from core.stt_whisper import get_whisper_engine
    except Exception as e:
        return f"whisper module load fail: {e}"
    eng = get_whisper_engine()
    avail = "OK" if eng.is_available() else "MISSING (pip install faster-whisper)"
    pref = _settings.get(_WHISPER_PREFERRED_KEY) or "google"
    return f"Whisper STT: {avail} · model: {eng.model_size} · current STT preference: {pref}"


@skill(
    name="whisper_transcribe_once",
    description="Record ~4 seconds of audio and transcribe via Whisper.",
    patterns=[
        "whisper transcribe", "transcribe with whisper",
        "whisper se transcribe karo",
        "whisper test", "test whisper",
    ],
    required_entities=[],
)
def whisper_transcribe_once(_slots: dict) -> str:
    try:
        from core.stt_whisper import get_whisper_engine
    except Exception as e:
        return f"whisper load fail: {e}"
    eng = get_whisper_engine()
    if not eng.is_available():
        return "Whisper unavailable. Install: 'pip install faster-whisper'."
    text = eng.transcribe_mic(4.0)
    if not text:
        return "Kuch sun nahi paya (ya transcribe fail)."
    return f"Whisper: {text}"


@skill(
    name="whisper_set_model",
    description="Switch Whisper model size — tiny/base/small/medium/large-v3.",
    patterns=[
        "set whisper model", "whisper model set karo",
        "use whisper tiny", "use whisper base", "use whisper small",
        "use whisper medium", "use whisper large",
        "whisper tiny model", "whisper base model",
    ],
    required_entities=[],
)
def whisper_set_model(slots: dict) -> str:
    text = (slots.get("raw_text") or slots.get("text") or "").lower()
    m = re.search(r"\b(tiny|base|small|medium|large(?:-v3)?)\b", text)
    if not m:
        return "Format: 'use whisper base' / 'use whisper small' etc."
    size = m.group(1)
    if size == "large":
        size = "large-v3"
    try:
        from core.stt_whisper import get_whisper_engine
    except Exception as e:
        return f"whisper load fail: {e}"
    ok, msg = get_whisper_engine().set_model_size(size)
    return msg


@skill(
    name="stt_prefer_whisper",
    description="Mark Whisper as the preferred STT backend in settings.",
    patterns=[
        "use whisper for stt", "prefer whisper",
        "whisper se sunoo", "switch stt to whisper",
        "whisper stt on", "use whisper stt",
    ],
    required_entities=[],
)
def stt_prefer_whisper(_slots: dict) -> str:
    _settings.set_(_WHISPER_PREFERRED_KEY, "whisper")
    return ("STT preference → Whisper. (voice_engine will switch on its "
            "next utterance if Whisper is installed.)")


@skill(
    name="stt_prefer_google",
    description="Mark Google as the preferred STT backend (default).",
    patterns=[
        "use google for stt", "prefer google stt",
        "switch stt to google", "google se sunoo",
        "default stt", "reset stt backend",
    ],
    required_entities=[],
)
def stt_prefer_google(_slots: dict) -> str:
    _settings.set_(_WHISPER_PREFERRED_KEY, "google")
    return "STT preference → Google."
