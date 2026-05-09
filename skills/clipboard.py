"""Clipboard read/write via pyperclip."""

from __future__ import annotations

from core.skill_registry import skill

try:
    import pyperclip
    _AVAILABLE = True
except ImportError:
    pyperclip = None
    _AVAILABLE = False


@skill(
    name="clipboard_copy",
    description="Copy a piece of text to the system clipboard",
    patterns=[
        "yeh copy karo",
        "isko copy kar lo",
        "copy this text",
        "clipboard pe daal do",
        "clipboard mein copy karo",
    ],
    required_entities=["content"],
    prompts={"content": "Kya copy karna hai?"},
)
def clipboard_copy(slots: dict) -> str:
    if not _AVAILABLE:
        return "pyperclip install nahi hai. 'pip install pyperclip' chalao."
    text = (slots.get("content") or "").strip()
    if not text:
        return "Kya copy karna hai? Text batao."
    pyperclip.copy(text)
    return f"Copy kar liya: {text[:60]}{'...' if len(text) > 60 else ''}"


@skill(
    name="clipboard_paste",
    description="Read the current clipboard contents",
    patterns=[
        "clipboard mein kya hai",
        "paste karo",
        "clipboard padho",
        "kya copy kiya tha",
        "show clipboard",
    ],
    required_entities=[],
)
def clipboard_paste(_slots: dict) -> str:
    if not _AVAILABLE:
        return "pyperclip install nahi hai. 'pip install pyperclip' chalao."
    text = pyperclip.paste() or ""
    if not text:
        return "Clipboard khaali hai."
    snippet = text[:200] + ("..." if len(text) > 200 else "")
    return f"Clipboard: {snippet}"
