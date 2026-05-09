"""Hindi ↔ English translation via Argos Translate (offline, free)."""

from __future__ import annotations

from core.skill_registry import skill

try:
    import argostranslate.translate as _argos_translate
    _AVAILABLE = True
except ImportError:
    _argos_translate = None
    _AVAILABLE = False


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
    required_entities=["query"],
    prompts={"query": "Kya translate karna hai?"},
)
def translate_to_english(slots: dict) -> str:
    if not _AVAILABLE:
        return "argostranslate install nahi hai. 'pip install argostranslate' chalao."
    text = (slots.get("query") or "").strip()
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
    required_entities=["query"],
    prompts={"query": "Kya translate karna hai?"},
)
def translate_to_hindi(slots: dict) -> str:
    if not _AVAILABLE:
        return "argostranslate install nahi hai. 'pip install argostranslate' chalao."
    text = (slots.get("query") or "").strip()
    if not text:
        return "Kya translate karna hai? Text batao."
    out = _translate(text, "en", "hi")
    return f"Translation: {out}" if out else "Translation engine ne kuch return nahi kiya."
