"""Persistent web-search knowledge cache.

Every successful `skills/web_search.py` lookup is written here keyed by a
normalized query hash. The next time the user asks the same thing, the
cache hits instantly and AERIS answers from "memory" instead of the
network.

Storage shape (`data/knowledge_cache.sqlite`):

    searches(
        query_hash       TEXT PRIMARY KEY,   -- sha1(normalized_query|mode)
        query            TEXT,               -- raw query as user spoke it
        query_norm       TEXT,               -- lowercased + whitespace-collapsed
        mode             TEXT,               -- "short" | "deep"
        response         TEXT,               -- the spoken/displayed summary
        sources_json     TEXT,               -- JSON list[ {title,url} ]
        created_at       REAL,               -- unix epoch
        last_hit_at      REAL,
        hit_count        INTEGER             -- how many times answered from cache
    )

Lookup is exact-match on (normalized_query, mode). Future enhancement:
fuzzy / semantic recall via the brain's existing sentence-transformer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

_DEFAULT_TTL_DAYS: float = 30.0  # 0 or negative = no expiry


@dataclass
class CachedAnswer:
    query: str
    mode: str
    response: str
    sources: list[dict]
    created_at: float
    hit_count: int

    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400.0


def _normalize(q: str) -> str:
    q = (q or "").strip().lower()
    q = re.sub(r"\s+", " ", q)
    # Strip trivial leading triggers so "search online ai" and "ai" hit the
    # same cache row. We only strip *leading* trigger phrases — the actual
    # subject (the part after the trigger) is what we key on.
    triggers = [
        "search online for", "search online", "search for", "search",
        "google karo", "google", "online dhundo", "internet pe dhundo",
        "internet pe", "internet par", "find online", "look up",
        "what is", "what's", "kya hai", "kya hota hai",
        "tell me about", "mujhe batao", "batao",
    ]
    sorted_triggers = sorted(triggers, key=len, reverse=True)
    # Iterate so stacked prefixes ("search online what is X") all peel off.
    for _ in range(6):
        matched = False
        for t in sorted_triggers:
            if q.startswith(t + " "):
                q = q[len(t) + 1:].strip()
                matched = True
                break
        if not matched:
            break
    # Strip trailing "in detail" / "deeply" / "vistar se" — those are mode
    # modifiers, not part of the topic.
    suffix_strip = [
        "in detail", "in depth", "deeply", "vistar se", "detail mein",
        "detail me", "more about", "extensively", "thoroughly",
    ]
    for s in sorted(suffix_strip, key=len, reverse=True):
        if q.endswith(" " + s):
            q = q[: -(len(s) + 1)].strip()
            break
    return q


def _hash(query_norm: str, mode: str) -> str:
    return hashlib.sha1(f"{query_norm}|{mode}".encode("utf-8")).hexdigest()


class KnowledgeCache:
    def __init__(self, db_path: str, ttl_days: float = _DEFAULT_TTL_DAYS):
        self.db_path = db_path
        self.ttl_days = ttl_days
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    query_hash    TEXT PRIMARY KEY,
                    query         TEXT NOT NULL,
                    query_norm    TEXT NOT NULL,
                    mode          TEXT NOT NULL,
                    response      TEXT NOT NULL,
                    sources_json  TEXT NOT NULL DEFAULT '[]',
                    created_at    REAL NOT NULL,
                    last_hit_at   REAL NOT NULL,
                    hit_count     INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_query_norm ON searches(query_norm)")

    def lookup(self, query: str, mode: str = "short") -> Optional[CachedAnswer]:
        norm = _normalize(query)
        if not norm:
            return None
        key = _hash(norm, mode)
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM searches WHERE query_hash = ?", (key,)
            ).fetchone()
        if not row:
            return None

        ans = CachedAnswer(
            query=row["query"],
            mode=row["mode"],
            response=row["response"],
            sources=json.loads(row["sources_json"] or "[]"),
            created_at=row["created_at"],
            hit_count=row["hit_count"],
        )
        if self.ttl_days > 0 and ans.age_days() > self.ttl_days:
            return None

        # Bump hit counter (best-effort; never block the caller).
        try:
            with self._conn() as c:
                c.execute(
                    "UPDATE searches SET hit_count = hit_count + 1, last_hit_at = ? "
                    "WHERE query_hash = ?",
                    (time.time(), key),
                )
        except sqlite3.Error:
            pass
        return ans

    def save(self, query: str, mode: str, response: str,
             sources: Optional[list[dict]] = None) -> None:
        if not query or not response:
            return
        norm = _normalize(query)
        if not norm:
            return
        key = _hash(norm, mode)
        now = time.time()
        sources_json = json.dumps(sources or [], ensure_ascii=False)
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO searches
                    (query_hash, query, query_norm, mode, response,
                     sources_json, created_at, last_hit_at, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(query_hash) DO UPDATE SET
                    response     = excluded.response,
                    sources_json = excluded.sources_json,
                    created_at   = excluded.created_at,
                    last_hit_at  = excluded.last_hit_at
                """,
                (key, query, norm, mode, response, sources_json, now, now),
            )

    def search_similar(self, query: str, limit: int = 5) -> list[CachedAnswer]:
        """Substring match on query_norm — used when the user asks something
        loosely related to a prior search ("tell me more about ai" should
        recall the cached "ai" entry)."""
        norm = _normalize(query)
        if not norm:
            return []
        like = f"%{norm}%"
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM searches WHERE query_norm LIKE ? "
                "ORDER BY last_hit_at DESC LIMIT ?",
                (like, limit),
            ).fetchall()
        out = []
        for r in rows:
            ans = CachedAnswer(
                query=r["query"], mode=r["mode"], response=r["response"],
                sources=json.loads(r["sources_json"] or "[]"),
                created_at=r["created_at"], hit_count=r["hit_count"],
            )
            if self.ttl_days > 0 and ans.age_days() > self.ttl_days:
                continue
            out.append(ans)
        return out

    def stats(self) -> dict:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) as n, COALESCE(SUM(hit_count),0) as hits "
                "FROM searches"
            ).fetchone()
            recent = c.execute(
                "SELECT query, mode, hit_count FROM searches "
                "ORDER BY last_hit_at DESC LIMIT 5"
            ).fetchall()
        return {
            "entries": row["n"],
            "total_hits": row["hits"],
            "recent": [dict(r) for r in recent],
        }

    def purge_expired(self) -> int:
        if self.ttl_days <= 0:
            return 0
        cutoff = time.time() - self.ttl_days * 86400
        with self._conn() as c:
            cur = c.execute("DELETE FROM searches WHERE created_at < ?", (cutoff,))
            return cur.rowcount

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM searches")


# Module-level singleton (lazy) so every skill shares one DB connection
# pool. The path is fixed relative to the project root — no env var dance.

_SINGLETON: Optional[KnowledgeCache] = None


def get_default_cache() -> KnowledgeCache:
    global _SINGLETON
    if _SINGLETON is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _SINGLETON = KnowledgeCache(os.path.join(root, "data", "knowledge_cache.sqlite"))
    return _SINGLETON


if __name__ == "__main__":
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "_kc_smoke.sqlite")
    if os.path.exists(tmp):
        os.remove(tmp)
    kc = KnowledgeCache(tmp, ttl_days=30)
    kc.save("what is ai", "short", "AI matlab artificial intelligence...",
            sources=[{"title": "Wiki", "url": "https://en.wikipedia.org/wiki/AI"}])
    hit = kc.lookup("Search online for AI")
    print("hit:", hit)
    print("stats:", kc.stats())
