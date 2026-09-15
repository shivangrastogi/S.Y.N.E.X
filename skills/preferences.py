"""Voice-controllable user preferences — wraps core.settings.

Maps a small whitelist of natural-language keys (name, city, voice gender,
default browser, focus pomodoro minutes) onto the underlying settings
store, so voice/text commands like:

    "set my name to Shivang"
    "remember my city is Mumbai"
    "what is my city"
    "default browser brave karo"
    "show my preferences"

…persist across restarts.

Whitelisted keys keep the surface small and safe — we don't want random
voice typos to mutate arbitrary internal settings (e.g. "remember health
endpoint is X" should NOT write `health_endpoint`).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)


# canonical_key -> set of voice-recognisable aliases. Lowercase.
_KEY_ALIASES: dict[str, set[str]] = {
    "user_name":         {"name", "my name", "naam", "mera naam"},
    "user_city":         {"city", "my city", "shahar", "mera shahar", "location", "place"},
    "default_browser":   {"browser", "default browser", "browser kaun sa",
                          "browser kaunsa", "default brwsr"},
    "voice_gender":      {"voice", "voice gender", "voice ka gender",
                          "jarvis voice", "tts voice"},
    "speech_rate":       {"speech rate", "voice speed", "speaking speed",
                          "tts rate", "tts speed"},
    "language":          {"language", "bhasha", "preferred language"},
    "focus_mode_pomodoro_min": {"pomodoro", "pomodoro minutes", "focus minutes",
                                "pomodoro time"},
}


def _canonical_key(spoken: str) -> Optional[str]:
    s = (spoken or "").strip().lower()
    if not s:
        return None
    for canon, aliases in _KEY_ALIASES.items():
        if s == canon or s in aliases:
            return canon
    # Loose match: "my X" where X is a key
    m = re.match(r"^(?:my|mera|meri|mere)\s+(.+)$", s)
    if m:
        return _canonical_key(m.group(1).strip())
    return None


_SET_RE = re.compile(
    r"^(?:please\s+)?"
    r"(?:set|remember|save|store|update|change)\s+"
    r"(?:my\s+|mera\s+|meri\s+|mere\s+)?"
    r"(?P<key>.+?)"
    r"\s+(?:to|=|is|as|ko)\s+"
    r"(?P<value>.+?)$",
    re.IGNORECASE,
)

_HINGLISH_SET_RE = re.compile(
    r"^(?P<value>.+?)\s+"
    r"(?:ko\s+)?(?P<key>.+?)\s+"
    r"(?:kar|set|save|store|update|yaad\s+rakh|yaad\s+rakho)$",
    re.IGNORECASE,
)

_GET_RE = re.compile(
    r"^(?:what(?:'s|\s+is)|kya\s+hai|batao)\s+(?:my\s+|mera\s+|meri\s+|mere\s+)?(?P<key>.+?)\??$",
    re.IGNORECASE,
)


def _parse_set(text: str) -> Optional[tuple[str, str]]:
    if not text:
        return None
    m = _SET_RE.search(text.strip())
    if m:
        return m.group("key").strip(), m.group("value").strip()
    m = _HINGLISH_SET_RE.search(text.strip())
    if m:
        return m.group("key").strip(), m.group("value").strip()
    return None


def _parse_get(text: str) -> Optional[str]:
    if not text:
        return None
    m = _GET_RE.search(text.strip())
    if m:
        return m.group("key").strip()
    return None


# ── set_preference ─────────────────────────────────────────────────


@skill(
    name="set_preference",
    description="Save a user preference (name/city/browser/voice/etc.) to settings.json.",
    patterns=[
        "set my name to Shivang",   # example
        "remember my name is Shivang",
        "remember my city as Mumbai",
        "set my city to Mumbai",
        "my city is Mumbai",
        "set default browser to brave",
        "default browser brave karo",
        "set voice gender female",
        "set pomodoro to 30",
        "remember my preferences",
        "update my preferences",
    ],
    required_entities=[],
)
def set_preference(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    parsed = _parse_set(text)
    if not parsed:
        return ("Samjha nahi — try: 'set my city to Mumbai' or "
                "'remember my name is Shivang'.")
    key_spoken, value_raw = parsed
    canon = _canonical_key(key_spoken)
    if not canon:
        keys_list = ", ".join(sorted(_KEY_ALIASES.keys()))
        return f"Ye preference yaad nahi rakhta: {key_spoken!r}. Allowed: {keys_list}"
    # Coerce numeric values where it makes sense.
    value: object = value_raw
    if canon in {"speech_rate", "focus_mode_pomodoro_min"}:
        try:
            value = int(value_raw)
        except ValueError:
            return f"{canon} ke liye number chahiye, mila {value_raw!r}."
    _settings.set_(canon, value)
    return f"Yaad rakh liya — {canon} = {value!r}."


# ── get_preference ─────────────────────────────────────────────────


@skill(
    name="get_preference",
    description="Read back a saved preference (name/city/browser/voice/etc.).",
    patterns=[
        "what's my name", "what is my name", "mera naam kya hai",
        "what's my city", "what is my city", "mera shahar kya hai", "mera city",
        "what is my browser", "default browser kya hai",
        "voice gender kya hai", "what voice am i using",
        "language kya hai", "preferred language batao",
        "pomodoro kitne minutes ka hai",
        "show preferences", "list preferences", "preferences dikhao",
    ],
    required_entities=[],
)
def get_preference(slots: dict) -> str:
    text = (slots.get("raw_text") or slots.get("text") or "").strip().lower()
    # Whole-catalog dump?
    if any(p in text for p in ("show preferences", "list preferences",
                                "preferences dikhao", "all preferences",
                                "my settings")):
        prefs = _settings.get_settings().all()
        if not prefs:
            return "Koi preference set nahi hai."
        lines = ["Saved preferences:"]
        for k in sorted(prefs):
            lines.append(f"  • {k} = {prefs[k]!r}")
        return "\n".join(lines)
    # Single key
    key_spoken = _parse_get(text)
    if not key_spoken:
        # Heuristic: drop "what" / "kya hai" / "batao" tokens then try
        # canonical lookup on the remainder.
        leftover = re.sub(
            r"\b(what'?s|what\s+is|kya\s+hai|batao|tell\s+me|mera|meri|mere|my)\b",
            "", text,
        ).strip(" ?")
        key_spoken = leftover
    canon = _canonical_key(key_spoken)
    if not canon:
        return f"Pata nahi {key_spoken!r} kya hai. Try 'show preferences' to list."
    val = _settings.get(canon)
    if val is None or val == "":
        return f"{canon} set nahi kiya hai. 'set my {key_spoken} to X' bolo."
    return f"{canon} = {val}."


# ── reset_preferences ──────────────────────────────────────────────


@skill(
    name="reset_preferences",
    description="Restore all preferences to their default values.",
    patterns=[
        "reset preferences", "preferences reset karo",
        "restore defaults", "default settings",
        "forget my preferences", "preferences clear karo",
    ],
    required_entities=[],
)
def reset_preferences(_slots: dict) -> str:
    _settings.get_settings().reset_to_defaults()
    return "Saari preferences default pe reset kar di."
