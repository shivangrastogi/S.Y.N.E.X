"""Multi-language TTS voice switching.

Sets ``tts_voice`` in settings; the TTS engine reads it on every
utterance so the change is instant. Voice names are Edge-TTS Neural
voice identifiers (`<locale>-<NameNeural>`); a curated alias map makes
the names easy to say.

Common aliases:
    "hindi female"   → "hi-IN-SwaraNeural"
    "hindi male"     → "hi-IN-MadhurNeural"
    "indian female"  → "en-IN-NeerjaNeural"   (default)
    "indian male"    → "en-IN-PrabhatNeural"
    "american female"→ "en-US-AriaNeural"
    "american male"  → "en-US-GuyNeural"
    "british female" → "en-GB-SoniaNeural"
    "british male"   → "en-GB-RyanNeural"

Skills:
  * ``tts_voice_set <alias|raw-name>``
  * ``tts_voice_list``
  * ``tts_voice_status`` / ``tts_voice_current``
  * ``tts_voice_reset``
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)


_VOICE_ALIASES: dict[str, str] = {
    # Hindi
    "hindi":            "hi-IN-SwaraNeural",
    "hindi female":     "hi-IN-SwaraNeural",
    "hindi swara":      "hi-IN-SwaraNeural",
    "hindi male":       "hi-IN-MadhurNeural",
    "hindi madhur":     "hi-IN-MadhurNeural",
    # Indian English
    "indian":           "en-IN-NeerjaNeural",
    "indian female":    "en-IN-NeerjaNeural",
    "neerja":           "en-IN-NeerjaNeural",
    "default":          "en-IN-NeerjaNeural",
    "indian male":      "en-IN-PrabhatNeural",
    "prabhat":          "en-IN-PrabhatNeural",
    # US English
    "american":         "en-US-AriaNeural",
    "us":               "en-US-AriaNeural",
    "american female":  "en-US-AriaNeural",
    "aria":             "en-US-AriaNeural",
    "american male":    "en-US-GuyNeural",
    "guy":              "en-US-GuyNeural",
    # UK English
    "british":          "en-GB-SoniaNeural",
    "uk":               "en-GB-SoniaNeural",
    "british female":   "en-GB-SoniaNeural",
    "sonia":            "en-GB-SoniaNeural",
    "british male":     "en-GB-RyanNeural",
    "ryan":             "en-GB-RyanNeural",
    # Gender-only fall-backs default to the Indian voices (assistant default region).
    "male voice":       "en-IN-PrabhatNeural",
    "male":             "en-IN-PrabhatNeural",
    "voice male":       "en-IN-PrabhatNeural",
    "female voice":     "en-IN-NeerjaNeural",
    "female":           "en-IN-NeerjaNeural",
    "voice female":     "en-IN-NeerjaNeural",
}


def _resolve_voice(text: str) -> Optional[str]:
    if not text:
        return None
    raw = text.strip()
    t = raw.lower()
    # Direct Neural voice id passed in raw? Pass through with ORIGINAL case
    # — Edge-TTS voice ids are case-sensitive.
    if re.match(r"^[a-z]{2}-[a-z]{2}-[a-z]+neural$", t):
        return raw
    # Sort aliases longest-first so "indian female" wins over "indian".
    for alias, vid in sorted(_VOICE_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in t:
            return vid
    return None


def _strip_set_verb(text: str) -> str:
    if not text:
        return ""
    return re.sub(
        r"^(?:please\s+)?"
        r"(?:set|change|switch|use)\s+"
        r"(?:tts\s+|voice\s+)?(?:to\s+)?(?:the\s+)?(?:voice\s+(?:to\s+)?)?",
        "", text.strip(), flags=re.IGNORECASE,
    ).strip(" .,?\"'")


# ── tts_voice_set ──────────────────────────────────────────────────


@skill(
    name="tts_voice_set",
    description="Switch the TTS voice. Accepts aliases (hindi/indian male/"
                "american female/etc.) or raw Edge-TTS neural names.",
    patterns=[
        "set voice to", "change voice to", "switch voice to",
        "use voice", "use hindi voice", "use american voice",
        "voice change karo", "voice set karo",
        "speak in hindi", "speak in english",
        "hindi voice me bolo", "american voice me bolo",
        "voice male karo", "voice female karo",
    ],
    required_entities=[],
)
def tts_voice_set(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    # Try direct alias lookup first; if that fails, strip verbs and retry.
    voice = _resolve_voice(text)
    if voice is None:
        voice = _resolve_voice(_strip_set_verb(text))
    if voice is None:
        return ("Voice samjha nahi. Try 'use hindi voice' or "
                "'set voice to american female'.")
    _settings.set_("tts_voice", voice)
    return f"TTS voice → {voice}."


# ── tts_voice_list ─────────────────────────────────────────────────


@skill(
    name="tts_voice_list",
    description="List the curated TTS voice aliases.",
    patterns=[
        "list voices", "list tts voices", "available voices",
        "voices dikhao", "kaunsi voices hain",
        "show voice options", "tts voice options",
    ],
    required_entities=[],
)
def tts_voice_list(_slots: dict) -> str:
    # Group by canonical voice id so duplicates collapse.
    by_id: dict[str, list[str]] = {}
    for alias, vid in _VOICE_ALIASES.items():
        by_id.setdefault(vid, []).append(alias)
    lines = [f"{len(by_id)} TTS voices available:"]
    for vid in sorted(by_id):
        aliases = sorted(by_id[vid])[:4]
        lines.append(f"  • {vid:28s} — {', '.join(aliases)}")
    lines.append("Use: 'set voice to <alias>' (e.g. 'set voice to hindi male').")
    return "\n".join(lines)


# ── tts_voice_status / current ─────────────────────────────────────


@skill(
    name="tts_voice_status",
    description="Report the currently selected TTS voice (language/accent). "
                "For rate+volume use 'voice status'.",
    patterns=[
        "tts voice status", "what tts voice am i using",
        "current tts voice", "tts voice batao",
        "kaunsi tts voice chal rahi hai",
        "tts current voice", "what's my tts voice",
    ],
    required_entities=[],
)
def tts_voice_status(_slots: dict) -> str:
    voice = _settings.get("tts_voice") or "en-IN-NeerjaNeural (default)"
    return f"Current TTS voice: {voice}."


# ── tts_voice_reset ────────────────────────────────────────────────


@skill(
    name="tts_voice_reset",
    description="Revert the TTS voice (language/accent) to the AERIS default "
                "(en-IN-NeerjaNeural). Note: separate from 'voice reset' "
                "which restores rate+volume.",
    patterns=[
        "reset tts voice", "tts voice reset", "default tts voice",
        "tts voice ko default karo", "reset voice language",
        "default voice language", "switch to default voice",
        "use default tts voice", "neerja voice me wapas jao",
    ],
    required_entities=[],
)
def tts_voice_reset(_slots: dict) -> str:
    _settings.set_("tts_voice", "")
    return "TTS voice → default (en-IN-NeerjaNeural)."
