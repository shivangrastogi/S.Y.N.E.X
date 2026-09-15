"""Transcript bus — fan-out for live STT events to UI subscribers.

Voice / STT subsystems push their results in via ``publish(text, role)``;
UI widgets (live transcript pane, future captions overlay) subscribe via
``add_listener(fn)`` and get every event as it lands. Decouples the
voice engine from any specific UI window.

Roles:
  * ``partial``  — interim hypothesis (Whisper / Vosk feed these as words come in)
  * ``final``    — committed user utterance
  * ``reply``    — AERIS' spoken response
  * ``system``   — internal narration (mic muted, etc.)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Optional

log = logging.getLogger(__name__)

_MAX_HISTORY = 500       # rolling cap


class TranscriptBus:
    def __init__(self):
        self._lock = threading.RLock()
        self._listeners: list[Callable[[dict], None]] = []
        self._history: deque[dict] = deque(maxlen=_MAX_HISTORY)

    def publish(self, text: str, role: str = "final") -> None:
        if not text:
            return
        evt = {"ts": time.time(), "text": str(text), "role": str(role)}
        with self._lock:
            self._history.append(evt)
            subs = list(self._listeners)
        for fn in subs:
            try:
                fn(evt)
            except Exception as e:
                log.debug("[transcript_bus] subscriber raised: %s", e)

    def add_listener(self, fn: Callable[[dict], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[dict], None]) -> bool:
        with self._lock:
            try:
                self._listeners.remove(fn)
                return True
            except ValueError:
                return False

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self._history)[-n:]

    def clear(self) -> int:
        with self._lock:
            n = len(self._history)
            self._history.clear()
        return n


_DEFAULT: Optional[TranscriptBus] = None


def get_bus() -> TranscriptBus:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = TranscriptBus()
    return _DEFAULT
