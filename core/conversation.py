"""Short-term conversation context.

Rolling buffer of the last N turns (user + assistant). Used by the LLM
chat fallback (C6) so chit-chat replies can stay coherent across turns.

Why a separate module from `memory.py`:
    - `memory` is durable, fact-shaped, JSON-backed, intentionally curated.
    - `conversation` is ephemeral, raw-text, in-memory, automatically cycled.

Format compatibility: `as_messages()` returns OpenAI / Ollama chat-style
messages so any LLM client can consume it without further mapping.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Turn:
    role: str       # "user" | "assistant"
    content: str
    timestamp: str  # ISO 8601
    sentiment: Optional[str] = None  # "positive" | "neutral" | "negative" | None


class ConversationHistory:
    def __init__(self, max_turns: int = 8):
        # max_turns counts complete user+assistant pairs;
        # internally we keep up to max_turns * 2 messages.
        self._buf: deque[Turn] = deque(maxlen=max_turns * 2)

    def add_user(self, text: str, sentiment_label: Optional[str] = None) -> None:
        self._buf.append(Turn(
            role="user",
            content=text,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            sentiment=sentiment_label,
        ))

    def add_assistant(self, text: str) -> None:
        self._buf.append(Turn(
            role="assistant",
            content=text,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        ))

    def as_messages(self) -> list[dict]:
        """OpenAI / Ollama chat-style: [{'role': ..., 'content': ...}, ...]."""
        return [{"role": t.role, "content": t.content} for t in self._buf]

    def last_user_sentiment(self) -> Optional[str]:
        for t in reversed(self._buf):
            if t.role == "user":
                return t.sentiment
        return None

    def __len__(self) -> int:
        return len(self._buf)

    def clear(self) -> None:
        self._buf.clear()


if __name__ == "__main__":
    h = ConversationHistory(max_turns=3)
    h.add_user("hello", sentiment_label="neutral")
    h.add_assistant("Hi! How can I help?")
    h.add_user("what's the weather", sentiment_label="neutral")
    h.add_assistant("Around 25 degrees.")
    h.add_user("thanks", sentiment_label="positive")
    h.add_assistant("Anytime!")
    h.add_user("open chrome", sentiment_label="neutral")  # will push out oldest
    h.add_assistant("Opening Chrome.")

    print(f"len = {len(h)} (max 6)")
    print(f"last user sentiment: {h.last_user_sentiment()}")
    for m in h.as_messages():
        print(f"  {m['role']:9s}: {m['content']}")
