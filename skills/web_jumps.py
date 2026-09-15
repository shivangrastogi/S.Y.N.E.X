"""Direct browser jumps — "google X" / "youtube X" / "maps X" / "wikipedia X".

Each one opens the default browser at the right destination URL. Distinct
from ``web_search.web_search`` (which fetches + summarizes a result) — these
just want the user dropped on the site so they can browse themselves.

The query is whatever follows the trigger word. Falls back to the home page
of the service if the user only says the trigger alone.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import webbrowser

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _strip_trigger(text: str, *triggers: str) -> str:
    """Lowercase text, peel any of the trigger phrases off the front, return
    the remaining query (also stripping common filler words)."""
    if not text:
        return ""
    lo = text.lower().strip()
    # Drop typical leading filler.
    lo = re.sub(r"^(please\s+|zara\s+|ek\s+baar\s+|abhi\s+)", "", lo)
    for trig in sorted(triggers, key=len, reverse=True):
        if lo.startswith(trig):
            return lo[len(trig):].strip(" :-,")
    return lo


def _open(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception as e:
        log.warning("[web_jumps] webbrowser.open failed for %s: %s", url, e)


# ── Google search ───────────────────────────────────────────────────


@skill(
    name="google_jump",
    description="Open Google search for the spoken query (or google.com if blank).",
    patterns=[
        "google", "google search", "open google", "google kholo",
        "search google for", "google karo", "google search karo",
        "google par search karo", "google par dhundo",
    ],
    required_entities=[],
)
def google_jump(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_trigger(
        text,
        "google search for", "search google for", "google par search karo",
        "google par dhundo", "google search karo", "google karo",
        "google kholo", "open google", "google search", "google",
    )
    if not query:
        _open("https://www.google.com")
        return "Google khol diya."
    _open("https://www.google.com/search?q=" + urllib.parse.quote_plus(query))
    return f"Google par {query!r} search kar raha hoon."


# ── YouTube ─────────────────────────────────────────────────────────


@skill(
    name="youtube_jump",
    description="Open YouTube search results for the spoken query.",
    patterns=[
        "youtube", "open youtube", "youtube kholo", "youtube par dikhao",
        "youtube search", "search youtube for", "youtube par search karo",
        "yt", "yt par", "youtube me dhundo",
    ],
    required_entities=[],
)
def youtube_jump(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_trigger(
        text,
        "search youtube for", "youtube par search karo", "youtube par dikhao",
        "youtube me dhundo", "youtube search", "youtube kholo",
        "open youtube", "youtube", "yt par", "yt",
    )
    if not query:
        _open("https://www.youtube.com")
        return "YouTube khol diya."
    _open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query))
    return f"YouTube par {query!r} dhund raha hoon."


# ── Google Maps ─────────────────────────────────────────────────────


@skill(
    name="maps_jump",
    description="Open Google Maps for the spoken location or directions.",
    patterns=[
        "maps", "open maps", "maps kholo", "google maps", "open google maps",
        "directions to", "navigate to", "show me on maps", "maps par dikhao",
        "ka location dikhao", "location dikhao",
    ],
    required_entities=[],
)
def maps_jump(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_trigger(
        text,
        "open google maps", "show me on maps", "maps par dikhao",
        "google maps", "directions to", "navigate to",
        "ka location dikhao", "location dikhao",
        "maps kholo", "open maps", "maps",
    )
    if not query:
        _open("https://www.google.com/maps")
        return "Google Maps khol diya."
    _open("https://www.google.com/maps/search/" + urllib.parse.quote_plus(query))
    return f"Maps par {query!r} dikha raha hoon."


# ── Wikipedia ───────────────────────────────────────────────────────


@skill(
    name="wikipedia_jump",
    description="Open Wikipedia article for the spoken topic.",
    patterns=[
        "wikipedia", "wiki", "open wikipedia", "wikipedia kholo",
        "wiki me dhundo", "wikipedia par dhundo", "wiki search",
        "ka wiki article dikhao",
    ],
    required_entities=[],
)
def wikipedia_jump(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_trigger(
        text,
        "wiki me dhundo", "wikipedia par dhundo", "wikipedia kholo",
        "ka wiki article dikhao", "open wikipedia", "wiki search",
        "wikipedia", "wiki",
    )
    if not query:
        _open("https://en.wikipedia.org/wiki/Main_Page")
        return "Wikipedia khol diya."
    _open("https://en.wikipedia.org/wiki/Special:Search?search=" + urllib.parse.quote_plus(query))
    return f"Wikipedia par {query!r} dhund raha hoon."


# ── Translate jump ──────────────────────────────────────────────────


@skill(
    name="translate_jump",
    description="Open Google Translate (with the spoken phrase pre-filled if any).",
    patterns=[
        "translate", "google translate", "open translate", "translate karo",
        "translate this", "translate kholo",
    ],
    required_entities=[],
)
def translate_jump(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_trigger(
        text,
        "google translate", "open translate", "translate karo",
        "translate this", "translate kholo", "translate",
    )
    if not query:
        _open("https://translate.google.com/")
        return "Google Translate khol diya."
    _open("https://translate.google.com/?text=" + urllib.parse.quote_plus(query))
    return f"Translate me {query!r} bhej diya."
