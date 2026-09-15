"""Hindi ↔ English translation via Argos Translate (offline, free)."""

from __future__ import annotations

import re

from core.skill_registry import skill

try:
    import argostranslate.translate as _argos_translate
    _AVAILABLE = True
except ImportError:
    _argos_translate = None
    _AVAILABLE = False


# Command/filler words peeled from the raw phrase to recover the payload when
# the extractor didn't fill `query` (it fills 0 of these skills' own patterns —
# the payload sits at either end: "hello ko hindi me translate karo" /
# "translate to hindi hello"). Same 'embedded argument' class as _fs_query.
_TR_STOP = {
    "translate", "translation", "karo", "kar", "do", "kardo", "hindi",
    "english", "angrezi", "angreji", "mein", "me", "mai", "ko", "ka", "ki",
    "kya", "hai", "bolo", "bol", "likho", "likh", "into", "to", "in",
    "convert", "mera", "meri", "batao", "bata", "please", "zara", "ye", "this",
}


def _tr_payload(slots: dict) -> str:
    q = (slots.get("query") or "").strip()
    if q:
        return q
    raw = (slots.get("raw_text") or slots.get("text") or "").strip()
    kept = [t for t in raw.split()
            if re.sub(r"[^a-z]", "", t.lower()) not in _TR_STOP]
    return " ".join(kept).strip()


def _translate(text: str, src: str, dst: str) -> str:
    if not _AVAILABLE:
        return ""
    try:
        return _argos_translate.translate(text, src, dst)
    except Exception:
        return ""


@skill(
    name="translate_to_english",
    description="Translate a Hindi or Hinglish phrase into English",
    patterns=[
        "english mein translate karo X",
        "X ko english mein bolo",
        "translate to english X",
        "X ka english kya hai",
    ],
    # No hard gate: payload lives in the phrase, not a `query` slot the extractor
    # fills — gating asks "kya translate?" and never reaches the handler (which
    # would give the actionable argostranslate-install hint). _tr_payload recovers it.
    required_entities=[],
    prompts={},
)
def translate_to_english(slots: dict) -> str:
    if not _AVAILABLE:
        return "argostranslate install nahi hai. 'pip install argostranslate' chalao."
    text = _tr_payload(slots)
    if not text:
        return "Kya translate karna hai? Text batao."
    out = _translate(text, "hi", "en") or _translate(text, "en", "hi")
    return f"Translation: {out}" if out else "Translation engine ne kuch return nahi kiya. Hindi-English models install hain?"


@skill(
    name="translate_to_hindi",
    description="Translate an English phrase into Hindi",
    patterns=[
        "hindi mein translate karo X",
        "X ko hindi mein bolo",
        "translate to hindi X",
        "X ka hindi kya hai",
    ],
    required_entities=[],
    prompts={},
)
def translate_to_hindi(slots: dict) -> str:
    if not _AVAILABLE:
        return "argostranslate install nahi hai. 'pip install argostranslate' chalao."
    text = _tr_payload(slots)
    if not text:
        return "Kya translate karna hai? Text batao."
    out = _translate(text, "en", "hi")
    return f"Translation: {out}" if out else "Translation engine ne kuch return nahi kiya."
