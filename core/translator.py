"""Text translator with a three-tier backend strategy.

  1. **LLM** (Ollama) when reachable — best quality + handles Hinglish.
  2. **argostranslate** if installed — fully offline.
  3. **Google Translate redirect** — falls back to opening a browser URL
     when nothing local works (last-resort, requires the user to read it).

Per-call language detection is intentionally crude — we just pass the
target language name through to the LLM / argos pair-lookup. Edge cases
(e.g. Marathi vs Hindi devanagari) are out of scope here.

Public API:
    translate(text, target_lang) -> tuple[str, str]   # (translation, backend_used)
    is_llm_available() -> bool
    is_argos_available() -> bool
"""
from __future__ import annotations

import logging
import urllib.parse
import webbrowser
from typing import Optional

log = logging.getLogger(__name__)


# Friendly name → ISO 639-1 code (used by argostranslate and the
# Google URL builder).
_LANG_CODES: dict[str, str] = {
    "english":   "en",
    "hindi":     "hi",
    "marathi":   "mr",
    "bengali":   "bn",
    "tamil":     "ta",
    "telugu":    "te",
    "gujarati":  "gu",
    "punjabi":   "pa",
    "spanish":   "es",
    "french":    "fr",
    "german":    "de",
    "italian":   "it",
    "portuguese": "pt",
    "russian":   "ru",
    "japanese":  "ja",
    "chinese":   "zh-CN",
    "korean":    "ko",
    "arabic":    "ar",
    "urdu":      "ur",
    "indonesian": "id",
    "dutch":     "nl",
    "polish":    "pl",
    "turkish":   "tr",
    "vietnamese": "vi",
}


def lang_code(name: str) -> str:
    """Canonicalise a language name to ISO code. Pass-through if already
    a code (2-3 chars). Returns 'en' as a safe default."""
    if not name:
        return "en"
    s = name.strip().lower()
    if s in _LANG_CODES:
        return _LANG_CODES[s]
    if len(s) in (2, 5) and "-" in s or len(s) == 2:
        return s
    # Loose prefix match
    for k, v in _LANG_CODES.items():
        if k.startswith(s):
            return v
    return "en"


def list_languages() -> list[str]:
    return sorted(_LANG_CODES.keys())


# ── backend availability ─────────────────────────────────────────


def is_llm_available() -> bool:
    try:
        from core.llm_chat import LLMChat
        return LLMChat().is_available()
    except Exception:
        return False


def is_argos_available() -> bool:
    try:
        import argostranslate.translate  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


# ── translation backends ─────────────────────────────────────────


def _via_llm(text: str, target_lang: str) -> Optional[str]:
    """Standalone tier-1: the embedded local model with a CLEAN prompt.

    Previously this went through the assistant chat path, which injected
    the whole AERIS persona ("sir", 2-short-sentences TTS rule, Hinglish
    style) into translations and truncated them at 120 tokens. The
    dedicated ``local_llm.generate`` has neither problem.
    """
    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            return None
        out = llm.generate(
            prompt=f"Text:\n{text}\n\nTranslate the text into "
                   f"{target_lang}.",
            system=("You are a precise translator. Reply with ONLY the "
                    "translation — no explanation, no quotes, no preamble."),
            max_tokens=min(500, max(80, len(text) // 2 + 60)),
            temperature=0.2,
        )
        return (out or "").strip() or None
    except Exception as e:
        log.info("[translator] LLM path failed: %s", e)
        return None


def _via_argos(text: str, target_lang: str) -> Optional[str]:
    try:
        import argostranslate.translate as at  # type: ignore
        # Argos works on installed language pairs; assume source=en if we
        # can't easily detect (Hinglish text often contains both).
        target = lang_code(target_lang)
        installed = at.get_installed_languages()
        from_lang = next((l for l in installed if l.code == "en"), None)
        to_lang   = next((l for l in installed if l.code == target), None)
        if from_lang is None or to_lang is None:
            return None
        translator = from_lang.get_translation(to_lang)
        if translator is None:
            return None
        return translator.translate(text)
    except Exception as e:
        log.info("[translator] argos path failed: %s", e)
        return None


def _via_google_redirect(text: str, target_lang: str) -> str:
    code = lang_code(target_lang)
    url = (f"https://translate.google.com/?sl=auto&tl={code}"
           f"&text={urllib.parse.quote(text)}&op=translate")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return f"(opened browser) → {url}"


# ── public translate() ───────────────────────────────────────────


def translate(text: str, target_lang: str = "english") -> tuple[str, str]:
    """Translate ``text`` into ``target_lang``. Returns (translation, backend).

    Backend strings: 'llm' | 'argos' | 'google_url' | 'noop'.
    """
    if not text:
        return "", "noop"
    # LLM first
    out = _via_llm(text, target_lang)
    if out:
        return out, "llm"
    # Argos
    out = _via_argos(text, target_lang)
    if out:
        return out, "argos"
    # Fallback browser redirect (the URL we built is itself the "answer").
    return _via_google_redirect(text, target_lang), "google_url"
