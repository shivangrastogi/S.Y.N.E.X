"""Translation voice surface.

Skills:
  * ``translate_to``        — "translate hello to french" / "translate yeh kaise bolte hain to hindi"
  * ``translate_clipboard`` — translate the current clipboard contents
  * ``translate_status``    — report which backends are reachable
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


_INTO_RE = re.compile(
    r"(?:into|to|in)\s+(?P<lang>[a-zA-Z\- ]+?)(?:\s+please)?\s*$",
    re.IGNORECASE,
)
_STRIP_RE = re.compile(
    r"^(?:please\s+)?"
    r"(?:translate\s+this|translate\s+text|translate)\s+",
    re.IGNORECASE,
)


def _parse(text: str) -> tuple[str, str]:
    """Return (body_to_translate, target_lang)."""
    if not text:
        return "", "english"
    s = _STRIP_RE.sub("", text.strip())
    m = _INTO_RE.search(s)
    if not m:
        return s.strip(), "english"
    lang = m.group("lang").strip().lower()
    body = s[: m.start()].strip(" ,.\"'")
    return body, lang or "english"


@skill(
    name="translate_to",
    description="Translate text into a target language. Format: "
                "'translate <text> to <language>'.",
    patterns=[
        "translate this to", "translate to",
        "translate text to", "translate me to",
        "translate this into", "translate into",
        "translate text into",
        "translate hello to french", "translate this in hindi",
    ],
    required_entities=[],
)
def translate_to(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    body, lang = _parse(text)
    if not body:
        return ("Format: 'translate <text> to <language>'. "
                "Example: 'translate hello to french'.")
    try:
        from core.translator import translate
    except Exception as e:
        return f"translator load fail: {e}"
    out, backend = translate(body, lang)
    return f"[{backend}] {out}"


@skill(
    name="translate_clipboard",
    description="Translate the current clipboard contents into a target "
                "language (default English).",
    patterns=[
        "translate clipboard", "translate clipboard to",
        "translate clipboard into", "clipboard translate karo",
        "clipboard ko translate karo",
    ],
    required_entities=[],
)
def translate_clipboard(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    # Parse target language from the text; the BODY here is the clipboard.
    _, lang = _parse(text)
    if not lang:
        lang = "english"
    try:
        import pyperclip  # type: ignore
    except Exception:
        return "pyperclip nahi mila — pip install pyperclip."
    try:
        body = pyperclip.paste() or ""
    except Exception as e:
        return f"clipboard read fail: {e}"
    if not body.strip():
        return "Clipboard khaali hai."
    try:
        from core.translator import translate
    except Exception as e:
        return f"translator load fail: {e}"
    out, backend = translate(body, lang)
    return f"[{backend} → {lang}] {out}"


@skill(
    name="translate_status",
    description="Report which translation backends (LLM / argos / Google URL) "
                "are reachable.",
    patterns=[
        "translate status", "translator status",
        "translation backends", "translate backends status",
        "kaunse translation backends chal rahe hain",
    ],
    required_entities=[],
)
def translate_status(_slots: dict) -> str:
    try:
        from core.translator import is_llm_available, is_argos_available, list_languages
    except Exception as e:
        return f"translator load fail: {e}"
    llm = "OK" if is_llm_available() else "down"
    argos = "OK" if is_argos_available() else "missing"
    google = "always (browser redirect)"
    langs = ", ".join(list_languages()[:12]) + ", …"
    return (f"LLM: {llm} · argos: {argos} · google: {google}\n"
            f"Languages: {langs}")
