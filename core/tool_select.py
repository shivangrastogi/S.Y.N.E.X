"""Relevance-based tool selection — the trick that makes a 1.5B agent work.

AERIS has ~400 registered tools. Handing the full manifest to the embedded
Qwen-1.5B is hopeless: the prompt alone would blow the 2048-token context,
and a small model picks garbage from a 400-item menu. This module cuts the
menu to the ≤12 tools that plausibly matter for THIS goal, using two cheap
signals:

    1. The intent brain's own top-3 for the utterance (it is literally a
       396-way relevance model — reuse it instead of inventing one).
    2. Token overlap between the goal text and each tool's name/description
       (catches step-2 tools the top-3 misses: "screenshot le aur phone pe
       bhejo" → "phone" pulls the bridge tools in).

Pure logic, no model loads — unit-tests in the fast lane. Called every
agent turn (goal + latest observation as the query), so the menu adapts as
the plan unfolds.
"""

from __future__ import annotations

import re
from typing import Optional

DEFAULT_K = 12

# Hinglish → tool-vocabulary hints. Tool names/descriptions are English;
# the goal is usually Hinglish. This tiny map bridges the obvious verbs —
# NOT a translator, just enough signal for overlap scoring.
_HINGLISH_HINTS = {
    "kholo": "open launch", "khol": "open", "chalao": "play run",
    "chala": "play run", "band": "close stop mute", "hatao": "close",
    "bajao": "play music", "gana": "music song", "gaana": "music song",
    "awaaz": "volume sound", "batao": "show info status", "dikhao": "show",
    "likho": "write note", "likh": "write note", "bhejo": "send",
    "bhej": "send", "yaad": "remind reminder", "dhundo": "search find",
    "dhund": "search find", "mausam": "weather", "tareekh": "date",
    "samay": "time", "photo": "screenshot picture", "le": "take",
    "lelo": "take", "kharcha": "expense", "kaam": "task",
}

_TOKEN_RE = re.compile(r"[a-z]+")

# Generic stopwords that would otherwise "match" half the manifest.
_STOP = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "with",
    "karo", "kar", "karke", "ke", "ka", "ki", "do", "de", "hai", "h",
    "mera", "meri", "mujhe", "please", "zara", "bhai", "yaar", "sir",
    "aur", "phir", "then", "current", "system",
}


def _tokens(text: str) -> set[str]:
    words = _TOKEN_RE.findall((text or "").lower())
    out: set[str] = set()
    for w in words:
        if w in _STOP or len(w) < 2:
            continue
        out.add(w)
        hint = _HINGLISH_HINTS.get(w)
        if hint:
            out.update(hint.split())
    return out


def select_tools(
    query: str,
    manifest: list[dict],
    top_intents: Optional[list[tuple[str, float]]] = None,
    k: int = DEFAULT_K,
) -> list[dict]:
    """Return the ≤k most relevant tool descriptors for ``query``.

    ``manifest``: [{"name", "description", "args"}, ...] (tools_manifest shape).
    ``top_intents``: the brain's top-3 [(intent, conf), ...] for the goal —
    tools whose name matches get a strong rank-weighted boost.
    Deterministic: ties break on manifest order.
    """
    if not manifest:
        return []
    if k <= 0 or len(manifest) <= k:
        return list(manifest)

    q_tokens = _tokens(query)
    intent_rank = {name: i for i, (name, _c) in enumerate(top_intents or [])}

    scored: list[tuple[float, int, dict]] = []
    for idx, tool in enumerate(manifest):
        name = str(tool.get("name", ""))
        score = 0.0
        # Signal 1 — the brain already ranked this tool for the utterance.
        if name in intent_rank:
            score += (3.0, 2.0, 1.5)[min(intent_rank[name], 2)]
        # Signal 2 — token overlap with name + description.
        name_tokens = set(name.lower().split("_")) - _STOP
        desc_tokens = _tokens(str(tool.get("description", "")))
        if q_tokens & name_tokens:
            score += 1.5 * len(q_tokens & name_tokens)
        if q_tokens & desc_tokens:
            score += 0.5 * len(q_tokens & desc_tokens)
        if score > 0:
            scored.append((score, idx, tool))

    scored.sort(key=lambda t: (-t[0], t[1]))
    picked = [t for _s, _i, t in scored[:k]]

    # Nothing matched at all (pure-Hinglish goal, odd vocab) → fall back to
    # the head of the manifest so the agent still has SOMETHING to work with.
    if not picked:
        return list(manifest[:k])
    return picked
