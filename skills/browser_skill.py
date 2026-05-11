"""Compound browser intents.

Voice:
    "open youtube in brave"
    "youtube ko edge mein kholo"
    "twitter open karo chrome ke profile 2 mein"
    "search ai in brave"
    "chrome profiles list karo"
    "set default browser brave"
"""

from __future__ import annotations

import logging
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import settings  # noqa: E402
from core.browser_launcher import (  # noqa: E402
    launch, list_known_browsers, list_profiles,
)
from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)


_BROWSER_TOKENS = {
    "chrome":  ("chrome", "google chrome"),
    "edge":    ("edge", "msedge", "microsoft edge", "ms edge"),
    "brave":   ("brave",),
    "firefox": ("firefox", "ff", "mozilla"),
    "opera":   ("opera",),
}


_SHORTCUT_URLS = {
    "youtube":   "https://www.youtube.com/",
    "yt":        "https://www.youtube.com/",
    "gmail":     "https://mail.google.com/",
    "gmail inbox": "https://mail.google.com/",
    "github":    "https://github.com/",
    "twitter":   "https://twitter.com/",
    "x":         "https://twitter.com/",
    "linkedin":  "https://www.linkedin.com/",
    "reddit":    "https://www.reddit.com/",
    "whatsapp":  "https://web.whatsapp.com/",
    "drive":     "https://drive.google.com/",
    "google drive": "https://drive.google.com/",
    "maps":      "https://maps.google.com/",
    "chatgpt":   "https://chat.openai.com/",
    "claude":    "https://claude.ai/",
    "notion":    "https://www.notion.so/",
    "instagram": "https://www.instagram.com/",
    "facebook":  "https://www.facebook.com/",
}


def _detect_browser(text: str) -> tuple[str, str]:
    """Find a browser mention; return (canonical, cleaned_text_with_browser_removed)."""
    if not text:
        return "", text
    t = text.lower()
    for canonical, hints in _BROWSER_TOKENS.items():
        for h in sorted(hints, key=len, reverse=True):
            pattern = r"\b" + re.escape(h) + r"\b(?:\s+browser)?"
            m = re.search(pattern, t)
            if m:
                cleaned = (text[:m.start()] + " " + text[m.end():]).strip()
                cleaned = re.sub(r"\s+", " ", cleaned)
                return canonical, cleaned
    return "", text


_PROFILE_RE_DIGIT = re.compile(r"\bprofile\s+(\d+)\b", re.IGNORECASE)
_PROFILE_RE_QUOTED = re.compile(r"\bprofile\s+['\"]([^'\"]{1,30})['\"]", re.IGNORECASE)
_PROFILE_RE_NAMED = re.compile(
    r"\bprofile\s+([A-Za-z][\w]*(?:\s+[A-Za-z][\w]*)?)",
    re.IGNORECASE,
)


def _extract_profile(text: str) -> tuple[str, str]:
    """Extract a profile reference. Supports: 'profile 1', 'profile "Work"',
    'profile work', 'profile shivang work'."""
    for rx in (_PROFILE_RE_QUOTED, _PROFILE_RE_DIGIT, _PROFILE_RE_NAMED):
        m = rx.search(text or "")
        if m:
            prof = m.group(1).strip().rstrip(".").rstrip(",")
            cleaned = (text[:m.start()] + " " + text[m.end():]).strip()
            cleaned = re.sub(r"\s+", " ", cleaned)
            return prof, cleaned
    return "", text


_OPEN_VERBS_RE = re.compile(
    r"\b(open|kholo|khol|launch|chalu|chalao|navigate to|go to|jao|kholna)\b",
    re.IGNORECASE,
)
_SEARCH_VERBS_RE = re.compile(
    r"\b(search|dhundo|google|find|look up|browse for)\b",
    re.IGNORECASE,
)
_FILLER_RE = re.compile(
    r"\b(in|me|mein|pe|par|the|a|an|do|please|sir|jarvis|aeris|ko|aur|and)\b",
    re.IGNORECASE,
)


def _extract_target(text: str) -> str:
    """Strip verbs / fillers / browser / profile and return the topic/URL."""
    t = text or ""
    t = _OPEN_VERBS_RE.sub(" ", t)
    t = _SEARCH_VERBS_RE.sub(" ", t)
    t = _FILLER_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip(" .,-:")


def _resolve_target(target: str, *, prefer_search: bool) -> tuple[str, bool]:
    """Return (url_or_query, is_search). Shortcut sites are matched verbatim."""
    if not target:
        return "", prefer_search
    low = target.lower().strip()
    if low in _SHORTCUT_URLS:
        return _SHORTCUT_URLS[low], False
    # Multi-word shortcuts (e.g. "google drive").
    for k, url in _SHORTCUT_URLS.items():
        if " " in k and k in low:
            return url, False
    if "." in target and " " not in target:
        return target, False
    return target, True if prefer_search else False


# --------------------------------------------------------------------------- #
#  Skills                                                                     #
# --------------------------------------------------------------------------- #

@skill(
    name="open_in_browser",
    description="Open a website or search a topic in a specific browser (and optionally a specific profile).",
    patterns=[
        "open youtube in brave", "open gmail in chrome",
        "open github in edge", "open twitter in brave browser",
        "youtube ko brave mein kholo", "gmail edge mein open karo",
        "open reddit in brave profile 2",
        "brave mein youtube kholo", "edge me github open karo",
        "chrome me whatsapp open karo",
        "open chatgpt in chrome",
        "search ai in brave", "brave mein ai search karo",
        "google ai in edge", "edge me ai dhundo",
        "open my work profile chrome and go to gmail",
        "open instagram in brave profile shivang",
    ],
    required_entities=[],
)
def open_in_browser(slots: dict) -> str:
    raw = " ".join(str(v) for v in slots.values() if v).strip() if slots else ""
    return _do_browser_open(raw, prefer_search=False)


@skill(
    name="search_in_browser",
    description="Search Google for a query in a specific browser (and optionally a specific profile).",
    patterns=[
        "search ai in brave", "search machine learning in chrome",
        "google python in edge", "brave mein search karo ai",
        "edge me dhundo machine learning", "chrome mein search karo python",
        "search in brave for openai", "find news in brave",
    ],
    required_entities=[],
)
def search_in_browser(slots: dict) -> str:
    raw = " ".join(str(v) for v in slots.values() if v).strip() if slots else ""
    return _do_browser_open(raw, prefer_search=True)


def _do_browser_open(raw: str, *, prefer_search: bool) -> str:
    if not raw:
        return "Kya open karna hai aur kis browser mein?"

    canonical, remainder = _detect_browser(raw)
    profile, remainder = _extract_profile(remainder)
    target = _extract_target(remainder)
    if not target and canonical:
        # User said "open chrome" with no target — just launch the browser homepage.
        target = "about:blank"

    url, is_search = _resolve_target(target, prefer_search=prefer_search)
    result = launch(url, browser=canonical or None, profile=profile or None,
                    is_search=is_search)

    if not result.ok:
        return f"Open nahi ho paya: {result.reason}"

    bits = []
    bits.append(f"Opened in {result.used_browser}")
    if result.used_profile:
        bits.append(f"profile '{result.used_profile}'")
    if target and target != "about:blank":
        bits.append(f"→ {target}")
    return " · ".join(bits) + "."


@skill(
    name="list_browser_profiles",
    description="List profiles configured in Chrome / Edge / Brave.",
    patterns=[
        "list chrome profiles", "chrome profiles batao",
        "edge profiles dikhao", "list brave profiles",
        "konse browser profiles hain", "show browser profiles",
        "browser profiles list",
    ],
    required_entities=[],
)
def list_browser_profiles(slots: dict) -> str:
    raw = " ".join(str(v) for v in slots.values()).lower() if slots else ""
    targets = []
    for b in list_known_browsers():
        if b in raw or not raw:
            targets.append(b)
    if not targets:
        targets = list_known_browsers()
    lines: list[str] = []
    for b in targets:
        profs = list_profiles(b)
        if not profs:
            continue
        lines.append(f"{b.title()}:")
        for p in profs:
            mark = "★" if (settings.get("default_browser_profile") or {}).get(b) == p.directory else " "
            lines.append(f"   {mark} {p.directory}  ({p.name})")
    return "\n".join(lines) if lines else "Koi browser profile detect nahi hua."


@skill(
    name="set_default_browser",
    description="Set the assistant's preferred browser for searches and URL opens.",
    patterns=[
        "set default browser brave", "default browser chrome karo",
        "make brave my default browser",
        "browser default brave set karo", "use chrome by default",
        "default browser edge karo",
    ],
    required_entities=[],
)
def set_default_browser(slots: dict) -> str:
    raw = " ".join(str(v) for v in slots.values()).lower() if slots else ""
    canonical, _ = _detect_browser(raw)
    if not canonical:
        return ("Kaunsa browser default karna hai? Available: " +
                ", ".join(list_known_browsers()))
    settings.set_("default_browser", canonical)
    return f"Default browser set: {canonical}."


@skill(
    name="set_default_profile",
    description="Remember a default Chrome / Edge / Brave profile so AERIS stops asking.",
    patterns=[
        "set default chrome profile 1", "default profile brave shivang work",
        "default chrome profile work karo",
        "use profile 2 for chrome by default",
        "edge default profile personal",
    ],
    required_entities=[],
)
def set_default_profile(slots: dict) -> str:
    raw = " ".join(str(v) for v in slots.values()) if slots else ""
    canonical, remainder = _detect_browser(raw)
    if not canonical:
        return "Kaunsa browser? (chrome, edge, brave)"
    profile_request, _ = _extract_profile(remainder)
    if not profile_request:
        # Fall back: last token is probably the profile.
        toks = remainder.split()
        profile_request = toks[-1] if toks else ""
    if not profile_request:
        return "Profile name ya number batao."
    from core.browser_launcher import profile_for
    resolved = profile_for(canonical, profile_request)
    if not resolved:
        return (f"{canonical.title()} mein '{profile_request}' profile nahi mila. "
                f"'list {canonical} profiles' bolo dekhne ke liye.")
    prefs = dict(settings.get("default_browser_profile") or {})
    prefs[canonical] = resolved
    settings.set_("default_browser_profile", prefs)
    return f"{canonical.title()} default profile: {resolved}."
