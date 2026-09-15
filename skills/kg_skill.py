"""Voice surface for the knowledge-graph memory.

Skills:
  * ``kg_remember``    — "remember that Sara is my sister"
  * ``kg_query``       — "who is Sara" / "where do I live"
  * ``kg_facts_about`` — "facts about Sara"
  * ``kg_forget``      — "forget Sara"
  * ``kg_list``        — list every stored triple
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _strip_lead(text: str, *triggers: str) -> str:
    if not text:
        return ""
    s = text.strip()
    sl = s.lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if sl.startswith(trig):
            return s[len(trig):].strip(" .,?\"'")
    return s


# ── kg_remember ────────────────────────────────────────────────────


@skill(
    name="kg_remember",
    description="Save a fact into the knowledge graph "
                "(e.g. 'remember that Sara is my sister').",
    patterns=[
        "remember that", "note that", "store that",
        "remember", "yaad rakho",
        "yaad rakh lo", "store fact", "save fact",
        "remember this fact", "kg add",
    ],
    required_entities=[],
)
def kg_remember(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    body = _strip_lead(
        text,
        "remember that", "note that", "store that", "save that",
        "yaad rakh lo", "yaad rakho",
        "kg add", "store fact", "save fact",
        "remember this fact", "remember",
    )
    if not body:
        return "Kya yaad rakhu? e.g. 'remember that Sara is my sister'."
    try:
        from core.kg_memory import get_kg
    except Exception as e:
        return f"kg_memory load fail: {e}"
    triples = get_kg().add_statement(body)
    if not triples:
        return "Yaad nahi rakh paya — phrasing samjha nahi."
    t = triples[0]
    return f"Yaad rakh liya: ({t['s']}) — [{t['p']}] → ({t['o']})"


# ── kg_query ───────────────────────────────────────────────────────


@skill(
    name="kg_query",
    description="Ask the knowledge graph a question — 'who is X', "
                "'where do I live', 'what's my Y'.",
    patterns=[
        "who is", "where do i live", "where do i work",
        "what is my", "what's my", "mera kya hai",
        "kya hai mera", "tell me about",
        "facts query", "kg query",
    ],
    required_entities=[],
)
def kg_query(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    if not text.strip():
        return "Sawal kya hai?"
    try:
        from core.kg_memory import get_kg
    except Exception as e:
        return f"kg_memory load fail: {e}"
    ans = get_kg().query(text)
    if ans is None:
        return "Pata nahi — kg me yeh fact nahi mila."
    return ans


# ── kg_facts_about ─────────────────────────────────────────────────


@skill(
    name="kg_facts_about",
    description="List every stored fact about a subject.",
    patterns=[
        "facts about", "tell me facts about",
        "facts of", "kg facts about",
        "what do you know about",
    ],
    required_entities=[],
)
def kg_facts_about(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _strip_lead(text, "facts about", "tell me facts about",
                       "what do you know about", "kg facts about",
                       "facts of")
    if not name:
        return "Kis ke baare me batao? e.g. 'facts about Sara'."
    try:
        from core.kg_memory import get_kg
    except Exception as e:
        return f"kg_memory load fail: {e}"
    facts = get_kg().facts_about(name)
    if not facts:
        return f"'{name}' ke baare me kuch yaad nahi hai."
    lines = [f"Facts about {name}:"]
    for t in facts:
        lines.append(f"  • [{t['p']}] {t['o']}")
    return "\n".join(lines)


# ── kg_forget ──────────────────────────────────────────────────────


@skill(
    name="kg_forget",
    description="Forget every stored fact about a subject.",
    patterns=[
        "forget about", "kg forget", "remove facts about",
        "kg ko bhul jao", "drop facts about",
        "forget all about",
    ],
    required_entities=[],
)
def kg_forget(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _strip_lead(text, "forget all about", "drop facts about",
                       "remove facts about", "kg ko bhul jao",
                       "kg forget", "forget about")
    if not name:
        return "Kis ko forget karu?"
    try:
        from core.kg_memory import get_kg
    except Exception as e:
        return f"kg_memory load fail: {e}"
    n = get_kg().forget(name)
    return f"Forgot {n} fact(s) about {name}."


# ── kg_list ────────────────────────────────────────────────────────


@skill(
    name="kg_list",
    description="List every stored knowledge-graph triple.",
    patterns=[
        "list knowledge", "kg list", "all facts",
        "show knowledge graph", "kg dump",
        "list all facts", "list memory",
    ],
    required_entities=[],
)
def kg_list(_slots: dict) -> str:
    try:
        from core.kg_memory import get_kg
    except Exception as e:
        return f"kg_memory load fail: {e}"
    triples = get_kg().all_triples()
    if not triples:
        return "Knowledge graph khaali hai. 'remember that ...' bolo to add karo."
    lines = [f"{len(triples)} fact(s) stored:"]
    for t in triples[:30]:
        lines.append(f"  • ({t['s']}) [{t['p']}] → ({t['o']})")
    if len(triples) > 30:
        lines.append(f"  ... + {len(triples) - 30} more")
    return "\n".join(lines)
