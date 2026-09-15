"""Preference learning — the fastest feedback loop (Blueprint learning loop 1).

When the user states a preference ("I prefer PhonePe", "mujhe dark theme pasand
hai", "next time use…"), AERIS writes it as a durable memory so the planner
recalls and respects it later (via ``MemoryFabric.recall_context``). This is how
the agent becomes *yours* over time.

Detection is deliberately CONSERVATIVE — only clear preference phrasings, never
command-ambiguous ones like "X ki jagah Y kholo" (which is an open-Y command, not
a preference). Pure + injectable so it unit-tests with a fake fabric.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# Clear preference markers only. "instead of" / "ki jagah" are intentionally
# excluded — they collide with real commands ("chrome ki jagah firefox kholo").
_PREF_RE = re.compile(
    r"\b("
    r"i\s+prefer|"
    r"prefer\s+\w+\s+over|"
    r"agli\s+baar|next\s+time|"
    r"mujhe\s+.+\s+(?:zyada\s+)?pasand|"
    r"i\s+(?:always|usually)\s+like"
    r")\b",
    re.I,
)


def detect_preference(text: str) -> Optional[str]:
    """Return the preference statement to remember, or None."""
    t = (text or "").strip()
    return t if _PREF_RE.search(t) else None


class PreferenceLearner:
    def __init__(self, *, fabric_provider: Optional[Callable[[], Any]] = None):
        self._fabric_provider = fabric_provider or _default_fabric

    def learn(self, text: str) -> Optional[str]:
        """If ``text`` states a preference, persist it and return it; else None."""
        pref = detect_preference(text)
        if not pref:
            return None
        try:
            self._fabric_provider().remember(f"Preference: {pref}", kind="note")
        except Exception as e:  # a store hiccup must never break the turn
            log.warning("[preference] store failed: %s", e)
            return None
        return pref


def ack(pref: str) -> str:
    """Short Hinglish acknowledgement for a captured preference."""
    return "Note kar liya — aage isko dhyaan rakhunga."


def _default_fabric() -> Any:
    from core import memory_fabric
    return memory_fabric.get_fabric()


_LEARNER: Optional[PreferenceLearner] = None


def get_learner() -> PreferenceLearner:
    global _LEARNER
    if _LEARNER is None:
        _LEARNER = PreferenceLearner()
    return _LEARNER
