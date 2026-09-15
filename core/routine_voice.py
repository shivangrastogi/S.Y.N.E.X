"""Routine offers, by voice — the user-facing verb layer for the learning loop.

The learner surfaces offers ("you start CODING ~10:00 most weekdays — automate
it?") and the graduation tracker turns repeated yes'es into live auto-routines
(``core.routine_offers`` / ``core.graduated_routines``). This module lets the
user drive that loop *out loud*:

* **accept**  "auto kar do" / "routine bana do" / "roz kar diya karo"
* **reject**  "rehne do" / "routine mat banao" / "nahi automate"
* **revert**  "morning routine band karo" / "auto band kar do" / "undo routine"

Resolution rules, kept deliberately conservative so a stray "band karo" (torch
off, panic, …) never touches a routine:

* accept / reject act on the **top pending offer** (highest confidence — the one
  just surfaced). Only the routine-management *verbs* trigger them, never a bare
  "haan", so this can't hijack an unrelated confirmation.
* revert needs an ``auto``/``routine`` word AND a stop word; if the user names a
  routine it's matched by token overlap, else the single running one is used and
  an ambiguous multi-match asks which.

Pure and injectable (all four collaborators pass in), so it unit-tests with
scripted offers and no tracker, engine, or model. ``handle()`` returns a spoken
reply string when it took the turn, or ``None`` to fall through to normal
handling.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

# accept: automate-this verbs (must mention auto/routine/roz-kar so it's specific)
_ACCEPT = re.compile(
    r"\b("
    r"auto\s*kar\s*(do|de|lo)|automate\s*(kar\s*do|it|karo)?|"
    r"routine\s*(bana\s*do|banao|set\s*kar\s*do|chalu\s*kar\s*do)|"
    r"(is[ek]?|isko|ise)\s*auto\s*(kar|bana)|"
    r"(har\s*(din|roz)|roz)\s*kar\s*(do|diya\s*karo|liya\s*karo)|"
    r"khud\s*kar\s*(liya|diya)\s*karo"
    r")\b",
    re.I,
)

# reject: don't-automate
_REJECT = re.compile(
    r"\b("
    r"routine\s*(mat|nahi)\s*(bana|banao|karo)|"
    r"(mat|nahi)\s*(bana|banao|automate)(\s*(routine|isko|ise))?|"
    r"(routine\s*)?rehne\s*do|no\s*automate|auto\s*mat\s*kar"
    r")\b",
    re.I,
)

# revert: stop a *running* auto-routine (needs an auto/routine word + a stop word)
_REVERT = re.compile(
    r"\b("
    r"(auto|automate|routine)\s*(band|off|stop|hata\s*do|hatao|delete|remove|undo)|"
    r"(band|off|stop|hata\s*do|hatao|delete|remove|undo)\s*(kar\s*(do|de)\s*)?"
    r"(?:\w+\s+){0,2}?(auto|automate|routine)"
    r")\b",
    re.I,
)

_STOP_WORDS = {"routine", "auto", "automate", "band", "off", "stop", "hata",
               "hatao", "do", "de", "kar", "karo", "the", "wo", "us", "delete",
               "remove", "undo", "mera", "meri", "wala", "wali", "ko"}


def classify(text: str) -> Optional[str]:
    """Which routine-management intent (if any) an utterance carries."""
    t = text or ""
    if _REVERT.search(t):
        return "revert"
    if _REJECT.search(t):
        return "reject"
    if _ACCEPT.search(t):
        return "accept"
    return None


def _name_tokens(text: str) -> List[str]:
    toks = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in toks if w not in _STOP_WORDS and len(w) > 2]


def _match_active(text: str, active: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the running auto-routine the user meant. Token overlap on
    name/key; if exactly one is running and the user named nothing, use it."""
    if not active:
        return None
    wanted = _name_tokens(text)
    if not wanted:
        return active[0] if len(active) == 1 else None
    best, best_score = None, 0
    for spec in active:
        hay = f"{spec.get('name', '')} {spec.get('key', '')}".lower()
        score = sum(1 for w in wanted if w in hay)
        if score > best_score:
            best, best_score = spec, score
    if best_score > 0:
        return best
    return active[0] if len(active) == 1 else None


def handle(text: str, *,
           pending_fn: Callable[[], List[Any]],
           active_fn: Callable[[], List[Dict[str, Any]]],
           accept_fn: Callable[[str], bool],
           reject_fn: Callable[[str], None],
           revert_fn: Callable[[str], None]) -> Optional[str]:
    """Handle a routine-management utterance. Returns a spoken reply if handled,
    else None so the caller continues normal processing."""
    intent = classify(text)
    if intent is None:
        return None

    if intent == "revert":
        active = list(active_fn() or [])
        if not active:
            return "Abhi koi auto-routine chal hi nahi raha."
        # ambiguous: several running and the user didn't name one
        if len(active) > 1 and not _name_tokens(text):
            names = ", ".join(s.get("name") or s.get("key") for s in active[:4])
            return f"Konsa band karun? Ye chal rahe hain: {names}."
        spec = _match_active(text, active)
        if spec is None:
            names = ", ".join(s.get("name") or s.get("key") for s in active[:4])
            return f"Konsa band karun? Ye chal rahe hain: {names}."
        revert_fn(spec.get("key"))
        return f"Theek hai, {spec.get('name') or 'wo routine'} band kar diya. Ab khud nahi chalega."

    pend = list(pending_fn() or [])
    if intent == "reject":
        if not pend:
            return "Abhi koi routine pending nahi hai."
        reject_fn(pend[0].key)
        return "Theek hai, nahi banaya."

    # accept
    if not pend:
        return "Abhi maine koi routine suggest nahi kiya."
    top = pend[0]
    newly = accept_fn(top.key)
    if newly:
        return f"Ho gaya — ab '{top.suggestion.title}' khud chalega."
    left = getattr(top, "accepts_left", 0)
    if left <= 0:
        return "Theek hai, note kar liya."
    more = "baar" if left == 1 else "baar"
    return (f"Theek hai. {left} aur {more} aisa hua to isko pakka auto kar dunga.")
