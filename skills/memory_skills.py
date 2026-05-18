"""Semantic-memory recall skills.

Every chat message goes through ``semantic_memory.add()`` automatically
(wired in ``main_window``); these skills just let the user query the
result.

* ``recall``       — "recall what I said about pomodoro" → top-k matches
* ``memory_stats`` — records / embedded / queue depth
"""
from __future__ import annotations

import logging
from datetime import datetime

from core import semantic_memory
from core.skill_registry import skill

log = logging.getLogger(__name__)


_RECALL_THRESHOLD = 0.35   # below this, treat as "no real match"


@skill(
    name="recall",
    description="Recall past conversations semantically (by meaning, not keyword)",
    patterns=[
        "recall", "remember when", "what did i say about",
        "find conversation", "search memory",
        "yaad karo", "yaad dilao", "memory search",
        "kya kaha tha", "remember the time",
    ],
    required_entities=["content"],
    prompts={"content": "Kya recall karna hai?"},
)
def recall(slots: dict) -> str:
    query = (slots.get("content") or "").strip()
    if len(query) < 3:
        return "Search query thodi bigger batao."
    mem = semantic_memory.get()
    hits = mem.recall(query, k=5, min_score=0.0)
    if not hits:
        return "Memory khaali hai ya encoder abhi load ho raha hai."
    # Filter to relevant hits but always return AT LEAST the top one so
    # the user can judge from the score.
    relevant = [(s, r) for s, r in hits if s >= _RECALL_THRESHOLD]
    if not relevant:
        top_score, top_rec = hits[0]
        return (f"Koi strong match nahi mila (best score {top_score:.2f}). "
                f"Closest: [{top_rec.role}] {top_rec.text[:120]}")
    out = [f"{len(relevant)} relevant match(es):"]
    for score, rec in relevant:
        ts = datetime.fromtimestamp(rec.ts).strftime("%b %d %H:%M")
        preview = rec.text[:90] + ("..." if len(rec.text) > 90 else "")
        out.append(f"  [{score:.2f}] {ts}  [{rec.role}] {preview}")
    return "\n".join(out)


@skill(
    name="memory_stats",
    description="Show semantic-memory size (records / embedded / queue)",
    patterns=[
        "memory stats", "memory size", "memory ka size",
        "kitni yaad hai", "memory info",
    ],
)
def memory_stats(_slots: dict) -> str:
    s = semantic_memory.get().stats()
    return (f"Semantic memory: {s['records']} records · "
            f"{s['with_embedding']} embedded · "
            f"{s['queue']} queued · dim={s['dim']}")
