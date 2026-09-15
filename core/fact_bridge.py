"""Fact bridge — quietly learns durable personal facts from CONVERSATION.

`UserMemory.detect_and_store` only fires on explicit memory *commands*
("remember that ...", "mera naam X hai"). But in real use people reveal
durable facts mid-chat without commanding anything:

    "yaar mujhe blue color bohot pasand hai"
    "my favourite editor is vscode"
    "i work at sehatup"
    "main flutter seekh raha hoon aajkal"

This module pattern-extracts such statements and writes them into the
knowledge graph (subject = "user"), so later "what's my favourite
editor" / "mujhe kya pasand hai" answers from the KG. Called from the
chat fallback path in ``main_engine`` — deterministic regex, ~0 ms,
silent (no ack; the structured log records what was learned).

Design constraints:
* HIGH precision over recall — a wrong "fact" pollutes memory. Patterns
  anchor on strong verb frames; free-form guessing is left to a future
  LLM-extraction pass (roadmap).
* Negations are rejected ("mujhe X pasand NAHI hai" must not store).
* Objects are length-capped so run-on sentences don't become facts.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

_MAX_OBJ_WORDS = 5

# Each rule: (compiled regex with one or two groups, predicate template).
# Two-group rules use group(1) as part of the predicate ("favourite X").
_RULES: list[tuple[re.Pattern, str]] = [
    # likes — Hinglish + English
    (re.compile(r"\bmujhe\s+(.{2,40}?)\s+(?:bohot\s+|bahut\s+)?pasand\s+hai\b",
                re.IGNORECASE), "likes"),
    (re.compile(r"\bi\s+(?:really\s+)?(?:like|love)\s+(?!to\b|it\b|this\b|that\b|you\b)"
                r"(.{2,40}?)(?:\s+(?:a lot|so much|yaar|man|bro))?[.!?]?$",
                re.IGNORECASE), "likes"),
    # favourite X is Y
    (re.compile(r"\bmy\s+favou?rite\s+([a-z ]{2,20}?)\s+is\s+(.{2,40}?)[.!?]?$",
                re.IGNORECASE), "favourite {}"),
    (re.compile(r"\bmera\s+favou?rite\s+([a-z ]{2,20}?)\s+(.{2,40}?)\s+hai\b",
                re.IGNORECASE), "favourite {}"),
    # work
    (re.compile(r"\bi\s+work\s+(?:at|for|in)\s+(.{2,40}?)[.!?]?$",
                re.IGNORECASE), "works at"),
    (re.compile(r"\bmain\s+(.{2,40}?)\s+(?:mein|me)\s+(?:kaam|job)\s+kart[ai]\s+hoon\b",
                re.IGNORECASE), "works at"),
    # learning
    (re.compile(r"\bi\s*(?:'m|\s+am)\s+learning\s+(.{2,40}?)(?:\s+(?:these days|nowadays|aajkal))?[.!?]?$",
                re.IGNORECASE), "learning"),
    (re.compile(r"\bmain\s+(.{2,40}?)\s+seekh\s+rah[ai]\s+hoon\b",
                re.IGNORECASE), "learning"),
    # birthday
    (re.compile(r"\bmy\s+birthday\s+is\s+(?:on\s+)?(.{2,25}?)[.!?]?$",
                re.IGNORECASE), "birthday"),
    (re.compile(r"\bmera\s+birthday\s+(.{2,25}?)\s+(?:ko|hai)\b",
                re.IGNORECASE), "birthday"),
]

_NEGATIONS = re.compile(r"\b(?:nahi|nahin|not|don'?t|never|na)\b", re.IGNORECASE)

# Object-side junk that means the "fact" is situational, not durable.
_JUNK_OBJECTS = re.compile(
    r"\b(?:it|this|that|you|kya|kuch|abhi|aaj|kal|right now|today)\b",
    re.IGNORECASE)


def _clean_obj(obj: str) -> Optional[str]:
    obj = obj.strip(" .,!?—-").strip()
    if not obj or len(obj.split()) > _MAX_OBJ_WORDS:
        return None
    if _JUNK_OBJECTS.fullmatch(obj):
        return None
    return obj


def extract_facts(text: str) -> list[tuple[str, str, str]]:
    """Return (subject, predicate, object) triples found in ``text``.
    Empty list when nothing matches the high-precision frames."""
    if not text or _NEGATIONS.search(text):
        return []
    out: list[tuple[str, str, str]] = []
    for rx, pred_tpl in _RULES:
        m = rx.search(text)
        if not m:
            continue
        if "{}" in pred_tpl:
            pred_part = m.group(1).strip().lower()
            obj = _clean_obj(m.group(2))
            if not obj or not pred_part or len(pred_part.split()) > 3:
                continue
            out.append(("user", pred_tpl.format(pred_part), obj))
        else:
            obj = _clean_obj(m.group(1))
            if not obj:
                continue
            out.append(("user", pred_tpl, obj))
    return out


def learn_from(text: str) -> int:
    """Extract + store facts into the knowledge graph. Returns count.
    Silent on the reply path; each stored fact emits a structured log
    event so the activity digest / change log can narrate it."""
    facts = extract_facts(text)
    if not facts:
        return 0
    stored = 0
    try:
        from core.kg_memory import get_kg
        kg = get_kg()
        for s, p, o in facts:
            try:
                kg.add_triple(s, p, o)
                stored += 1
                log.info("[fact_bridge] learned: %s — %s — %s", s, p, o)
                try:
                    from core.log_setup import event
                    event("fact_learned", predicate=p, obj=o)
                except Exception:
                    pass
            except Exception as e:
                log.debug("[fact_bridge] store failed: %s", e)
    except Exception as e:
        log.debug("[fact_bridge] kg unavailable: %s", e)
    return stored
