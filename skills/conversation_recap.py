"""Conversation recap — read the last N exchanges back to the user.

Uses the process-wide ConversationHistory published by the main engine
via ``core.conversation.set_active`` (see iter#2). When no engine is
attached (e.g. fresh boot, tests), reports the empty state cleanly.

Skills:
  * ``conversation_recap`` — last N exchanges as readable transcript
  * ``conversation_clear`` — wipe the active history (UI clear_chat is
                            a different sentinel — this just clears the
                            engine's rolling buffer)
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.conversation import get_active
from core.skill_registry import skill

log = logging.getLogger(__name__)


_HOW_MANY_RE = re.compile(
    r"\b(?:last|recent|recently|kitne|pichle|last\s+few)?\s*(\d+)\b",
    re.IGNORECASE,
)


def _extract_count(text: str, default: int = 4) -> int:
    if not text:
        return default
    m = _HOW_MANY_RE.search(text)
    if not m:
        return default
    n = int(m.group(1))
    return max(1, min(20, n))


@skill(
    name="conversation_recap",
    description="Repeat the last N user/assistant exchanges so you remember "
                "what was just discussed.",
    patterns=[
        "recap", "conversation recap", "what did we talk about",
        "kya baat ki thi", "pichli baat batao",
        "what did i just ask", "last few turns",
        "show recent conversation", "recap last 3", "show last 5",
        "recap last exchanges", "pichle kya bola tha",
    ],
    required_entities=[],
)
def conversation_recap(slots: dict) -> str:
    hist = get_active()
    if hist is None:
        return "Active conversation nahi hai — engine attached nahi."
    text = slots.get("raw_text") or slots.get("text") or ""
    n = _extract_count(text, default=4)
    msgs = hist.as_messages()
    if not msgs:
        return "Abhi tak koi conversation nahi hua."
    # Take the last 2N entries (pairs) — round up so a dangling user turn
    # still shows.
    tail = msgs[-(2 * n):]
    lines = [f"Last {min(n, len(tail))} exchange(s):"]
    for m in tail:
        role = "you" if m.get("role") == "user" else "AERIS"
        body = (m.get("content") or "").strip().replace("\n", " ")
        if len(body) > 120:
            body = body[:117] + "..."
        lines.append(f"  {role}: {body}")
    return "\n".join(lines)


@skill(
    name="conversation_clear",
    description="Wipe the rolling ConversationHistory buffer (does NOT clear "
                "the chat panel — see clear_chat for that).",
    patterns=[
        "clear conversation memory", "forget conversation",
        "conversation history clear",
        "purani baatein bhool jao", "history clear karo",
        "wipe conversation memory",
    ],
    required_entities=[],
)
def conversation_clear(_slots: dict) -> str:
    hist = get_active()
    if hist is None:
        return "Koi active conversation history nahi."
    n_before = len(hist)
    try:
        hist.clear()
    except Exception as e:
        return f"Clear fail: {e}"
    return f"Conversation memory cleared ({n_before} turns dropped)."
