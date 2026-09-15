"""Clipboard intelligence — AERIS ka apna dimag, clipboard par.

Jo bhi copy kiya hai usko: summarize / professional rewrite / bullet
points / extract (numbers, emails, links). Summarize-rewrite-bullets
embedded LOCAL model se (core/local_llm.generate — koi API nahi);
extract pure regex hai (LLM ki zaroorat hi nahi). Kuch bhi machine se
bahar nahi jaata.
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)

_MAX_CLIP_CHARS = 6000


def _clip() -> str:
    try:
        import pyperclip
        return (pyperclip.paste() or "").strip()
    except Exception as e:
        log.debug("[clipboard_ai] paste failed: %s", e)
        return ""


def _generate(prompt: str, system: str, max_tokens: int = 260) -> str | None:
    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            return None
        return llm.generate(prompt=prompt, system=system,
                            max_tokens=max_tokens, temperature=0.3)
    except Exception as e:
        log.debug("[clipboard_ai] llm failed: %s", e)
        return None


def _llm_over_clip(system: str, task: str, max_tokens: int = 260) -> str:
    text = _clip()
    if not text:
        return "Clipboard khaali hai, sir — pehle kuch copy karo."
    if len(text) > _MAX_CLIP_CHARS:
        text = text[:_MAX_CLIP_CHARS]
    out = _generate(f"TEXT:\n{text}\n\n{task}", system, max_tokens)
    if not out:
        return ("Local model abhi available nahi — data/models/llm/ mein "
                ".gguf chahiye.")
    return out.strip()


@skill(
    name="clipboard_summarize",
    description="Summarise the copied text fully on-device (embedded LLM).",
    patterns=[
        "clipboard ka summary do", "copied text summarize karo",
        "clipboard summary", "jo copy kiya uska summary do",
        "copied text ka saar batao", "clipboard ka saar do",
    ],
    required_entities=[],
)
def clipboard_summarize(_slots: dict) -> str:
    return _llm_over_clip(
        system=("Summarise in 3-5 short lines: core point pehle, phir key "
                "details. Hinglish theek hai. No preamble."),
        task="Summarise this text.")


@skill(
    name="clipboard_rewrite",
    description="Rewrite the copied text in clear professional English (on-device).",
    patterns=[
        "clipboard professional banao", "clipboard rewrite karo",
        "copied text professional english me likho",
        "clipboard ko professional bana do", "isko professional likho clipboard se",
        "clipboard polish karo",
    ],
    required_entities=[],
)
def clipboard_rewrite(_slots: dict) -> str:
    return _llm_over_clip(
        system=("Rewrite the text in clear, polite, professional English. "
                "Keep the meaning and all facts exactly. Reply with ONLY "
                "the rewritten text."),
        task="Rewrite this text professionally.", max_tokens=340)


@skill(
    name="clipboard_bullets",
    description="Turn the copied text into crisp bullet points (on-device).",
    patterns=[
        "clipboard bullets banao", "clipboard se points banao",
        "copied text ke bullet points banao", "clipboard ko points me todo",
        "bullet points banao clipboard se",
    ],
    required_entities=[],
)
def clipboard_bullets(_slots: dict) -> str:
    return _llm_over_clip(
        system=("Convert into 3-7 crisp bullet points, one line each, "
                "starting with '- '. Keep every number and name. "
                "Hinglish theek hai."),
        task="Convert this text into bullet points.")


_NUM_RE = re.compile(r"(?<![\w.])[+-]?\d[\d,]*(?:\.\d+)?%?(?![\w.])")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")


@skill(
    name="clipboard_extract",
    description="Pull numbers, emails, links, and phone numbers out of the copied text (pure regex, instant).",
    patterns=[
        "clipboard se numbers nikalo", "clipboard se emails nikalo",
        "clipboard extract karo", "clipboard ke links nikalo",
        "copied text se number nikalo", "clipboard se phone number nikalo",
    ],
    required_entities=[],
)
def clipboard_extract(slots: dict) -> str:
    text = _clip()
    if not text:
        return "Clipboard khaali hai, sir — pehle kuch copy karo."
    asked = (slots.get("raw_text") or "").lower()
    parts: list[str] = []

    def _clean(vals: list) -> list[str]:
        out, seen = [], set()
        for v in vals:
            v = str(v).strip().rstrip(".,;:)")
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return out[:12]

    phones = _clean(re.sub(r"[\s-]", "", p) for p in _PHONE_RE.findall(text))
    phone_digits = {re.sub(r"\D", "", p) for p in phones}
    emails = _clean(_EMAIL_RE.findall(text))
    links = _clean(_URL_RE.findall(text))
    # Numbers: drop anything that is just a fragment of a found phone
    # number, and bare country codes — they're noise, not data.
    numbers = [n for n in _clean(_NUM_RE.findall(text))
               if re.sub(r"\D", "", n) not in phone_digits
               and not any(re.sub(r"\D", "", n) and
                           re.sub(r"\D", "", n) in pd for pd in phone_digits)
               and n not in ("+91", "91")]

    def _grab(label: str, vals: list[str], want: bool):
        if want and vals:
            parts.append(f"{label}: " + ", ".join(vals))

    want_all = not any(k in asked for k in ("number", "email", "link", "phone"))
    _grab("phones", phones, want_all or "phone" in asked)
    _grab("emails", emails, want_all or "email" in asked)
    _grab("links", links, want_all or "link" in asked)
    _grab("numbers", numbers,
          want_all or ("number" in asked and "phone" not in asked))
    if not parts:
        return "Clipboard mein koi number, email, link ya phone nahi mila."
    return "\n".join(parts)
