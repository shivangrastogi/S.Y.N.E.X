"""Reasoning cache — stable-reply memoization for the weak local model (issue #7).

The embedded 1.5B model is fine for chat but slow and inconsistent on repeats.
This caches its replies to STABLE, non-stateful questions (definitions, "explain
X", general knowledge) keyed by a normalized query, so asking the same thing twice
is instant and consistent.

SAFETY — the whole point: it must never serve a STALE answer. So it refuses to
cache anything whose answer depends on live state — time/date, battery, weather,
files, prices, counts, "abhi/aaj", etc. Callers must also only offer it the purely
conversational path (Interpreter plan == "chat"). TTL-bounded + LRU-evicted.
Disable via `AERIS_REASONING_CACHE_OFF=1`.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import OrderedDict
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "reasoning_cache.json")

_TTL_S = 86_400.0      # 24h — long enough for stable facts, short enough to bound drift
_MAX = 500

# Words that make an answer depend on live/changing state → NEVER cache these.
_STATEFUL = re.compile(
    r"\b(time|abhi|aaj|kal|date|din|baje|battery|charge|weather|mausam|news|khabar|"
    r"stock|price|rate|kitne|kitna|kitni|kaunsa|konsa|konsi|file|files|downloads|"
    r"screen|kaha|kahan|where|status|online|available|latest|newest|today|now|"
    r"current|abhi\s?ka|remaining|bacha|left)\b", re.I)


def _norm(query: str) -> str:
    return " ".join((query or "").lower().strip().split()).rstrip("?!. ")


def is_cacheable(query: str) -> bool:
    """A query is cacheable only if its answer is stable — not about live state,
    and substantive enough to be worth memoizing."""
    q = (query or "").strip()
    if len(q.split()) < 2:                 # trivial one-word — not worth it
        return False
    return not _STATEFUL.search(q)


class ReasoningCache:
    def __init__(self, path: Optional[str] = None, enabled: Optional[bool] = None,
                 ttl_s: float = _TTL_S, max_entries: int = _MAX):
        self._path = path or _PATH
        if enabled is None:
            enabled = os.environ.get("AERIS_REASONING_CACHE_OFF", "") not in ("1", "true", "True")
        self.enabled = enabled
        self._ttl = ttl_s
        self._max = max_entries
        self._data: "OrderedDict[str, list]" = OrderedDict()   # key -> [reply, ts]
        self._since_persist = 0
        self._load()

    def get(self, query: str, *, now: Optional[float] = None) -> Optional[str]:
        if not self.enabled:
            return None
        import time as _t
        now = _t.time() if now is None else now
        k = _norm(query)
        e = self._data.get(k)
        if not e:
            return None
        reply, ts = e[0], e[1]
        if (now - ts) > self._ttl:          # stale → drop it
            self._data.pop(k, None)
            return None
        self._data.move_to_end(k)           # LRU touch
        return reply

    def put(self, query: str, reply: str, *, now: Optional[float] = None) -> None:
        if not self.enabled or not reply or not is_cacheable(query):
            return
        import time as _t
        now = _t.time() if now is None else now
        k = _norm(query)
        self._data[k] = [reply, now]
        self._data.move_to_end(k)
        while len(self._data) > self._max:  # evict the oldest
            self._data.popitem(last=False)
        self._since_persist += 1
        if self._since_persist >= 10:
            self._since_persist = 0
            self.persist()

    # ── persistence ──────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            for k, v in d.items():
                self._data[k] = [v[0], float(v[1])]
        except Exception:
            pass

    def persist(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(dict(self._data), fh)
            os.replace(tmp, self._path)
        except Exception as e:
            log.debug("[reasoning_cache] persist failed: %s", e)


_DEFAULT: Optional[ReasoningCache] = None


def get() -> ReasoningCache:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ReasoningCache()
    return _DEFAULT
