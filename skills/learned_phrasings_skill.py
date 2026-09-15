"""Inspect and undo what AERIS learned from your rephrasings (§6.24).

`core/repair_memory.py` quietly rewrites routing based on corrections — which
is only safe if you can see what it did and take it back. This is that window.

**One skill, not three.** Show / forget-one / forget-all are sub-commands
parsed out of the raw text rather than separate intents, because
`docs/ROUTING_ACCURACY_AUDIT.md` traces the measured 50% routing accuracy to
587-intent corpus bloat. Adding three near-identical intents to a corpus whose
diagnosed problem *is* too many near-identical intents would make the thing
this feature exists to help slightly worse. Patterns are also anchored on
"phrasing"/"seekha" rather than bare "forget"/"bhool", which `kg_skill`,
`preferences`, `custom_gestures_skill` and `conversation_recap` already own.
"""
from __future__ import annotations

import logging
import re

from core.repair_memory import get_active
from core.skill_registry import skill

log = logging.getLogger(__name__)

_FORGET_ALL_RE = re.compile(
    r"\b(all|sab|sabhi|everything|puri list|clear)\b", re.IGNORECASE)
# "clear" and "reset" belong here as well as in _FORGET_ALL_RE — this is the
# gate that decides show-vs-forget at all, so leaving them out made the
# registered pattern "clear learned phrasings" fall through to *show*.
_FORGET_RE = re.compile(
    r"\b(forget|bhool|unlearn|hata|remove|delete|clear|reset|wipe|"
    r"mat\s+seekh)\b", re.IGNORECASE)
_OFF = ("Self-correction abhi off hai, sir — koi phrasing seekhi nahi gayi. "
        "Chalu karne ke liye AERIS_REPAIR_MEMORY=1 set karo.")


def _show(mem) -> str:
    if not len(mem):
        return ("Abhi tak koi phrasing nahi seekhi, sir. Jab koi command miss "
                "hoti hai aur aap use dobara kehte ho, main wahi yaad rakhta hoon.")
    rows = mem.items()                       # most-used first
    lines = [f"{len(rows)} phrasing{'s' if len(rows) != 1 else ''} seekhi hain:"]
    for phrase, a in rows[:15]:
        used = f", {a.hits}x use hui" if a.hits else ""
        lines.append(f"  • \"{phrase}\" → {a.intent}{used}")
    if len(rows) > 15:
        lines.append(f"  … aur {len(rows) - 15} aur.")
    lines.append("Kisi ko hatane ke liye: \"woh phrasing bhool jao\".")
    return "\n".join(lines)


def _forget(mem, text: str) -> str:
    # "sab bhool jao" — the whole table.
    if _FORGET_ALL_RE.search(text or ""):
        n = len(mem)
        mem.clear()
        return (f"{n} seekhi hui phrasing hata di, sir." if n
                else "Hatane ke liye kuch tha hi nahi, sir.")

    # A quoted phrase wins over everything — it is unambiguous.
    quoted = re.search(r"[\"'“”‘’](.+?)[\"'“”‘’]", text or "")
    if quoted:
        target = quoted.group(1).strip()
        if mem.forget(target):
            return f"\"{target}\" bhool gaya, sir."
        return (f"\"{target}\" meri seekhi hui list me nahi hai, sir. "
                "Poori list dekhne ke liye: \"kya phrasings seekhi hain\".")

    # Otherwise: the most recent thing learned. This is also the sensible
    # default for a bare "forget that phrasing" — the user is almost always
    # reacting to the lesson AERIS just drew.
    gone = mem.forget_last()
    if gone:
        return f"Theek hai — \"{gone}\" wapas bhool gaya, sir."
    return ("Abhi haal me kuch seekha nahi tha, sir. Kisi ek ko hatana ho "
            "to use quotes me likho: forget \"chrome band karo\".")


@skill(
    name="learned_phrasings",
    description="Show the command phrasings AERIS taught itself from your "
                "corrections, and forget any of them.",
    patterns=[
        "what phrasings have you learned", "learned phrasings",
        "show learned phrasings", "which phrasings did you learn",
        "kaunsi phrasing seekhi", "tumne kya phrasing seekhi",
        # NOT "kya seekha tumne" — `learning_status` owns that one, and the
        # collision guard (tests/test_pattern_collisions.py) enforces it.
        "seekhi hui commands dikhao",
        "forget that phrasing", "unlearn that phrasing",
        "woh phrasing bhool jao", "ye phrasing bhool jao",
        "sab seekhi phrasings hata do", "clear learned phrasings",
    ],
    required_entities=[],
)
def learned_phrasings(slots: dict) -> str:
    mem = get_active()
    if mem is None:
        return _OFF
    text = (slots or {}).get("raw_text", "") or ""
    try:
        if _FORGET_RE.search(text):
            return _forget(mem, text)
        return _show(mem)
    except Exception as e:                    # never let inspection break a turn
        log.warning("[learned_phrasings] failed: %s", e)
        return "Seekhi hui list padhne me dikkat aa gayi, sir."
