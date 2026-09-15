"""Undo stack for reversible skill actions.

Some skills change state the user might immediately regret — overwriting the
clipboard, changing volume, forgetting a memory. This module is a tiny LIFO
ring buffer of *reversible* actions: a skill that did something undoable calls
``record(label, undo_fn)``; a later "undo" / "wait no" pops the newest entry
and runs its ``undo_fn``.

Contract for ``undo_fn``:
  * takes no arguments (capture state via a default-arg closure),
  * performs the reversal,
  * returns a short human message describing what it undid.

It is intentionally **opt-in** — only skills that register an undo participate,
so the long tail of irreversible actions (kill_process, screenshot) never
pretend to be undoable. A voice "undo" honours a generous time window; the GUI
toast can pass a tight one (``within_s=5``).

Process-local singleton, thread-safe, no persistence (undo is a within-session
affordance). Pure stdlib — unit-testable with fake undo callables.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger(__name__)

DEFAULT_WINDOW_S = 180.0   # how long a voice "undo" reaches back by default
_MAXLEN = 20


@dataclass
class UndoableAction:
    label: str
    undo: Callable[[], str]
    skill: str = ""
    ts: float = field(default_factory=time.time)


class ActionHistory:
    def __init__(self, maxlen: int = _MAXLEN):
        self._buf: deque[UndoableAction] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def record(self, label: str, undo: Callable[[], str], skill: str = "") -> None:
        if not callable(undo):
            raise TypeError("undo must be callable")
        with self._lock:
            self._buf.append(UndoableAction(label=label, undo=undo, skill=skill))

    def peek_last(self) -> Optional[UndoableAction]:
        with self._lock:
            return self._buf[-1] if self._buf else None

    def labels(self) -> list[str]:
        """Human labels of pending undoable actions, newest first."""
        with self._lock:
            return [a.label for a in reversed(self._buf)]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def undo_last(self, within_s: Optional[float] = DEFAULT_WINDOW_S) -> str:
        """Pop the newest action and run its undo. Returns a human message.

        ``within_s=None`` means no time limit. If the newest action is older
        than the window it is *not* popped (the user can still see it via
        ``peek_last``), keeping a stale "undo" from silently reverting
        something from an hour ago.
        """
        with self._lock:
            if not self._buf:
                return "Undo karne ke liye kuch nahi hai, sir."
            action = self._buf[-1]
            if within_s is not None and (time.time() - action.ts) > within_s:
                age = int(time.time() - action.ts)
                return (f"Last action ('{action.label}') {age}s purana hai — "
                        f"undo window nikal gaya. Phir bhi chahiye to bolo "
                        f"'force undo'.")
            self._buf.pop()

        try:
            msg = action.undo()
        except Exception as e:                       # undo itself failed
            log.warning("[action_history] undo of %r failed: %s", action.label, e)
            return f"Undo fail ho gaya ({action.label}): {e}"
        return msg or f"Undo kar diya: {action.label}."


# ── module-level singleton + convenience API ──────────────────────────── #

_HISTORY = ActionHistory()


def record(label: str, undo: Callable[[], str], skill: str = "") -> None:
    _HISTORY.record(label, undo, skill)


def undo_last(within_s: Optional[float] = DEFAULT_WINDOW_S) -> str:
    return _HISTORY.undo_last(within_s)


def peek_last() -> Optional[UndoableAction]:
    return _HISTORY.peek_last()


def labels() -> list[str]:
    return _HISTORY.labels()


def clear() -> None:
    _HISTORY.clear()


def history() -> ActionHistory:
    """The process-wide singleton (handy for tests that want isolation)."""
    return _HISTORY
