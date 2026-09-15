"""Dictionary skills — define a word, synonyms, antonyms.

Backed by https://dictionaryapi.dev (free, no API key). Cached per word
for 30 minutes so a hot lookup is instant and rate limits aren't hit.

Skills:
  * ``define_word`` — "what does X mean" / "define X" / "X ka matlab"
  * ``synonyms``    — "synonyms of X" / "X ke synonyms"
  * ``antonyms``    — "antonyms of X"
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_API = "https://api.dictionaryapi.dev/api/v2/entries/en/"
_TTL_S = 30 * 60
_CACHE: dict[str, tuple[float, dict | None]] = {}


def _strip_verb(text: str, *triggers: str) -> str:
    if not text:
        return ""
    s = text.strip()
    s_lo = s.lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if s_lo.startswith(trig):
            return s[len(trig):].strip(" :,.?\"'")
    # Trailing-verb forms: "X ka matlab" / "X ke synonyms"
    s = re.sub(
        r"\s+(?:ka\s+matlab|ka\s+meaning|ke\s+synonyms|ke\s+antonyms|"
        r"matlab|meaning|definition|synonyms|antonyms)$",
        "", s, flags=re.IGNORECASE,
    )
    return s.strip(" :,.?\"'")


def _fetch(word: str) -> dict | None:
    key = word.lower().strip()
    if not key:
        return None
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and (now - cached[0]) < _TTL_S:
        return cached[1]
    url = _API + urllib.parse.quote(key)
    try:
        with urllib.request.urlopen(url, timeout=4.0) as r:
            data = json.loads(r.read())
    except Exception as e:
        log.info("[dictionary] fetch failed for %r: %s", key, e)
        _CACHE[key] = (now, None)
        return None
    # API returns a list of entries (one per recorded spelling). Pick the first.
    if isinstance(data, list) and data:
        _CACHE[key] = (now, data[0])
        return data[0]
    _CACHE[key] = (now, None)
    return None


def _collect_meanings(entry: dict) -> list[tuple[str, str]]:
    """Return [(part_of_speech, definition), ...] from a dictionaryapi entry."""
    out: list[tuple[str, str]] = []
    for meaning in entry.get("meanings") or []:
        pos = meaning.get("partOfSpeech") or "?"
        for d in meaning.get("definitions") or []:
            txt = (d.get("definition") or "").strip()
            if txt:
                out.append((pos, txt))
    return out


def _collect_related(entry: dict, key: str) -> list[str]:
    """key in {"synonyms", "antonyms"}. Walks meanings + definitions."""
    seen: list[str] = []
    for meaning in entry.get("meanings") or []:
        for s in meaning.get(key) or []:
            if s and s not in seen:
                seen.append(s)
        for d in meaning.get("definitions") or []:
            for s in d.get(key) or []:
                if s and s not in seen:
                    seen.append(s)
    return seen


# ── define_word ────────────────────────────────────────────────────


@skill(
    name="define_word",
    description="Look up a word's definition (dictionaryapi.dev).",
    patterns=[
        "define", "definition of", "what does X mean", "meaning of",
        "X ka matlab", "X ka meaning",
        "what is the meaning of", "explain the word",
        "lookup word", "dictionary lookup",
    ],
    required_entities=[],
)
def define_word(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    word = _strip_verb(
        text,
        "what does the word", "what does", "what is the meaning of",
        "what is the definition of", "what's the meaning of",
        "definition of", "meaning of",
        "define the word", "define",
        "explain the word", "explain",
        "lookup word", "dictionary lookup",
        "X ka matlab", "X ka meaning",
    )
    # Trailing " mean" / " mean?" / "?" cleanup.
    word = re.sub(r"\s+mean\??$", "", word, flags=re.IGNORECASE).strip()
    if not word:
        return "Kaunsa word define karna hai? e.g. 'define ephemeral'."
    entry = _fetch(word)
    if not entry:
        return f"'{word}' dictionary mein nahi mila (ya internet down hai)."
    meanings = _collect_meanings(entry)
    if not meanings:
        return f"'{word}' ke liye koi definition nahi mili."
    lines = [f"{word}:"]
    for pos, defn in meanings[:3]:
        lines.append(f"  ({pos}) {defn}")
    return "\n".join(lines)


# ── synonyms ───────────────────────────────────────────────────────


@skill(
    name="synonyms",
    description="List synonyms for a word.",
    patterns=[
        "synonyms of", "synonyms for", "X ke synonyms",
        "similar words to", "synonym",
        "what's another word for", "another word for",
    ],
    required_entities=[],
)
def synonyms(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    word = _strip_verb(
        text,
        "what's another word for", "another word for",
        "similar words to", "similar word for",
        "synonyms of", "synonyms for", "synonym of", "synonym for",
        "synonyms", "synonym",
    )
    if not word:
        return "Kaunsa word? e.g. 'synonyms of happy'."
    entry = _fetch(word)
    if not entry:
        return f"'{word}' lookup fail — dictionary ya internet check karo."
    syns = _collect_related(entry, "synonyms")
    if not syns:
        return f"'{word}' ke koi synonyms registered nahi hain."
    return f"{word} → " + ", ".join(syns[:12])


# ── antonyms ───────────────────────────────────────────────────────


@skill(
    name="antonyms",
    description="List antonyms (opposite-meaning words) for a word.",
    patterns=[
        "antonyms of", "antonyms for", "opposite of",
        "X ke antonyms", "X ka opposite",
        "what's the opposite of", "antonym",
    ],
    required_entities=[],
)
def antonyms(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    word = _strip_verb(
        text,
        "what's the opposite of", "opposite of",
        "antonyms of", "antonyms for", "antonym of", "antonym for",
        "antonyms", "antonym",
    )
    if not word:
        return "Kaunsa word? e.g. 'antonyms of happy'."
    entry = _fetch(word)
    if not entry:
        return f"'{word}' lookup fail."
    ants = _collect_related(entry, "antonyms")
    if not ants:
        return f"'{word}' ke koi antonyms registered nahi hain."
    return f"{word} ↔ " + ", ".join(ants[:12])
