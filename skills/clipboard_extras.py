"""Clipboard extras — speak / size / quick-stats for the current clipboard.

Distinct from ``skills/clipboard.py`` (copy + paste) and
``skills/clipboard_history.py`` (rolling buffer). These are
introspection / output-oriented skills.
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)

try:
    import pyperclip  # type: ignore
    _AVAILABLE = True
except Exception:
    pyperclip = None
    _AVAILABLE = False


def _safe_paste() -> str:
    if not _AVAILABLE:
        return ""
    try:
        return pyperclip.paste() or ""
    except Exception as e:
        log.info("[clipboard_extras] paste failed: %s", e)
        return ""


# ── clipboard_say ──────────────────────────────────────────────────


@skill(
    name="clipboard_say",
    description="Speak the current clipboard text aloud (truncated to ~400 chars).",
    patterns=[
        "say clipboard", "read clipboard", "speak clipboard",
        "clipboard padho aloud", "clipboard ko bolo", "clipboard read karo",
        "read out clipboard", "read what's in clipboard",
        "tell me clipboard", "clipboard sunao",
    ],
    required_entities=[],
)
def clipboard_say(_slots: dict) -> str:
    if not _AVAILABLE:
        return "pyperclip nahi mila — pip install pyperclip."
    text = _safe_paste()
    if not text:
        return "Clipboard khaali hai."
    # The TTS engine speaks the response we return. Truncate so a 10 MB
    # paste doesn't lock the speaker for 20 minutes.
    snippet = text.strip()
    if len(snippet) > 400:
        snippet = snippet[:400].rstrip() + "..."
    return snippet


# ── clipboard_stats ────────────────────────────────────────────────


@skill(
    name="clipboard_stats",
    description="Quick stats about the current clipboard (chars, words, lines).",
    patterns=[
        "clipboard size", "clipboard stats", "clipboard mein kitne characters",
        "how big is clipboard", "clipboard ka size",
        "clipboard count", "clipboard length",
        "kitne words clipboard mein",
    ],
    required_entities=[],
)
def clipboard_stats(_slots: dict) -> str:
    if not _AVAILABLE:
        return "pyperclip nahi mila — pip install pyperclip."
    text = _safe_paste()
    if not text:
        return "Clipboard khaali hai."
    n_chars = len(text)
    n_words = len(text.split())
    n_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    preview = text[:80].replace("\n", " ")
    if len(text) > 80:
        preview += "..."
    return (f"Clipboard: {n_chars} chars · {n_words} words · {n_lines} lines\n"
            f"Preview: {preview}")


# ── clipboard_url ──────────────────────────────────────────────────


@skill(
    name="clipboard_open_url",
    description="Open the URL currently in clipboard in the default browser.",
    patterns=[
        "open clipboard url", "open url from clipboard", "clipboard url kholo",
        "open the link in my clipboard", "browser mein clipboard kholo",
        "go to clipboard url", "open copied link",
    ],
    required_entities=[],
)
def clipboard_open_url(_slots: dict) -> str:
    if not _AVAILABLE:
        return "pyperclip nahi mila — pip install pyperclip."
    text = _safe_paste().strip()
    if not text:
        return "Clipboard khaali hai."
    if not (text.lower().startswith(("http://", "https://"))
            or text.lower().startswith("www.")):
        # Allow bare domains like "github.com"
        if "." not in text or " " in text:
            return f"Clipboard mein valid URL nahi hai: {text[:60]!r}"
    url = text if text.lower().startswith(("http://", "https://")) else "https://" + text
    try:
        import webbrowser
        webbrowser.open(url)
        return f"Browser mein khol diya: {url}"
    except Exception as e:
        return f"URL kholne mein fail: {e}"
