"""Semantic recall over conversation history.

Stores ``(timestamp, role, text, embedding)`` records and lets the user
query them later with natural language:

    semantic_memory.add("user", "let's start pomodoro mode at 7pm")
    ...
    semantic_memory.recall("when did we talk about pomodoro?")
    # → top-k records sorted by cosine similarity

Key design decisions
--------------------
* **Reuses the brain's existing sentence encoder** — no second model
  load. The encoder is ``paraphrase-multilingual-MiniLM-L12-v2``,
  already in RAM after brain boot. We pull it lazily from
  ``JarvisBrain.classifier.encoder`` so this module costs zero extra
  memory at idle.
* **Embeddings are computed on a background thread** so a chatty
  session doesn't block the GUI. The text-only record is enqueued
  immediately; the embedding is filled in asynchronously and merged
  back under a lock.
* **Persists to ``data/semantic_memory.npz``** — atomic via
  ``np.savez_compressed`` to a temp path + ``os.replace``. Backed by
  the same in-memory ring buffer; load is one-shot on first access.
* **Bounded** — keeps the last 2000 records (~5-10 MB on disk).

The threshold-free contract: ``recall`` always returns SOMETHING (top-k
matches by similarity), so callers can decide whether the top match is
relevant. Skill bindings surface the score so the user judges.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STORE_PATH = os.path.join(_ROOT, "data", "semantic_memory.npz")

_MAX_RECORDS = 2000
_DIM_DEFAULT = 384   # MiniLM-L12-v2 output dim — overridden on first encode


# ── Dataclass ──────────────────────────────────────────────────────── #

@dataclass
class _Record:
    ts: float
    role: str           # "user" | "ai" | "system"
    text: str
    # Embedding filled in asynchronously; None until the worker thread gets to it.
    emb: Optional["any"] = None


# ── Store ──────────────────────────────────────────────────────────── #

class SemanticMemory:
    """Process-wide singleton — use ``get()`` to access."""

    def __init__(self):
        self._lock = threading.RLock()
        self._records: list[_Record] = []
        self._dim: int = _DIM_DEFAULT
        self._encoder = None
        self._embed_q: "queue.Queue[_Record]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._dirty = False
        self._last_save_ts = 0.0
        self._loaded = False

    # ── lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the embedding worker thread. Idempotent. Loads from disk
        on first call.
        """
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            self._load_from_disk()
            self._worker = threading.Thread(
                target=self._run, name="SemanticMemory", daemon=True,
            )
            self._worker.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        # Wake the worker out of its queue.get(timeout=0.5) cycle.
        try: self._embed_q.put_nowait(None)  # type: ignore[arg-type]
        except Exception: pass
        t = self._worker
        if t and t.is_alive():
            t.join(timeout=timeout)
        # Final flush so anything buffered hits disk.
        try:
            self._save_to_disk()
        except Exception:
            pass

    # ── public API ─────────────────────────────────────────────────

    def add(self, role: str, text: str) -> None:
        """Enqueue a new record. Embedding fills in asynchronously."""
        text = (text or "").strip()
        if not text or len(text) < 3:
            return
        rec = _Record(ts=time.time(), role=role, text=text)
        with self._lock:
            self._records.append(rec)
            if len(self._records) > _MAX_RECORDS:
                self._records = self._records[-_MAX_RECORDS:]
            self._dirty = True
        try:
            self._embed_q.put_nowait(rec)
        except queue.Full:
            pass

    def recall(self, query: str, k: int = 5,
               *, min_score: float = 0.0) -> list[tuple[float, _Record]]:
        """Top-k records by cosine similarity to ``query``. Returns
        ``(score, record)`` pairs in DESCENDING score order.

        ``min_score`` filters out results below that threshold — set to
        ~0.45 to keep only "actually relevant" matches when surfacing
        to the user (and ``0.0`` to always return something).
        """
        query = (query or "").strip()
        if not query:
            return []
        if not self._ensure_encoder():
            return []
        try:
            import numpy as np
            q_emb = self._encoder.encode([query], normalize_embeddings=True)[0]
        except Exception as e:
            log.warning("[semantic_mem] encode query failed: %s", e)
            return []
        with self._lock:
            scored: list[tuple[float, _Record]] = []
            for rec in self._records:
                if rec.emb is None:
                    continue
                score = float(np.dot(q_emb, rec.emb))
                if score >= min_score:
                    scored.append((score, rec))
        scored.sort(key=lambda t: -t[0])
        return scored[:k]

    def stats(self) -> dict:
        with self._lock:
            with_emb = sum(1 for r in self._records if r.emb is not None)
            return {
                "records": len(self._records),
                "with_embedding": with_emb,
                "queue": self._embed_q.qsize(),
                "dim": self._dim,
            }

    # ── worker thread ──────────────────────────────────────────────

    def _run(self) -> None:
        # Wait briefly so the brain has time to load its encoder before
        # we try to grab it.
        if self._stop.wait(1.0):
            return
        while not self._stop.is_set():
            try:
                rec = self._embed_q.get(timeout=0.5)
            except queue.Empty:
                # Periodic flush: every 30 s if dirty.
                if self._dirty and (time.time() - self._last_save_ts) > 30:
                    try: self._save_to_disk()
                    except Exception: log.exception("[semantic_mem] save raised")
                continue
            if rec is None:
                continue
            if not self._ensure_encoder():
                # Re-enqueue and back off — brain not ready yet.
                try: self._embed_q.put_nowait(rec)
                except Exception: pass
                if self._stop.wait(2.0):
                    return
                continue
            try:
                emb = self._encoder.encode([rec.text],
                                           normalize_embeddings=True)[0]
                with self._lock:
                    rec.emb = emb
                    self._dim = len(emb)
                    self._dirty = True
            except Exception as e:
                log.warning("[semantic_mem] encode raised: %s", e)

    def _ensure_encoder(self) -> bool:
        if self._encoder is not None:
            return True
        # Try to reuse the running brain's encoder — no second model load.
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                for w in app.topLevelWidgets():
                    brain_worker = getattr(w, "_brain", None)
                    engine = getattr(brain_worker, "_engine", None)
                    if engine and getattr(engine, "brain", None):
                        enc = engine.brain.classifier.encoder
                        if enc is not None:
                            self._encoder = enc
                            return True
        except Exception:
            pass
        # Headless fallback — load our own (only during tests / smoke).
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            return True
        except Exception as e:
            log.debug("[semantic_mem] no encoder available yet: %s", e)
            return False

    # ── persistence ────────────────────────────────────────────────

    def _load_from_disk(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(_STORE_PATH):
            return
        try:
            import numpy as np
            with np.load(_STORE_PATH, allow_pickle=True) as data:
                texts = list(data.get("texts", []))
                roles = list(data.get("roles", []))
                tss = list(data.get("ts", []))
                embs = data.get("emb")
            n = min(len(texts), len(roles), len(tss))
            for i in range(n):
                rec = _Record(
                    ts=float(tss[i]),
                    role=str(roles[i]),
                    text=str(texts[i]),
                    emb=(embs[i] if embs is not None
                                and i < len(embs)
                                and embs[i] is not None
                                and len(embs[i]) > 0
                         else None),
                )
                self._records.append(rec)
            log.info("[semantic_mem] loaded %d records (%d embedded)",
                     len(self._records),
                     sum(1 for r in self._records if r.emb is not None))
        except Exception as e:
            log.warning("[semantic_mem] load failed: %s", e)

    def _save_to_disk(self) -> None:
        with self._lock:
            if not self._dirty or not self._records:
                return
            recs = list(self._records)
            self._dirty = False
            self._last_save_ts = time.time()
        try:
            import numpy as np
            os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
            texts = np.array([r.text for r in recs], dtype=object)
            roles = np.array([r.role for r in recs], dtype=object)
            tss = np.array([r.ts for r in recs], dtype=np.float64)
            # Pad missing embeddings with empty arrays so positional indexing matches.
            emb_arr: list = []
            for r in recs:
                emb_arr.append(r.emb if r.emb is not None else np.array([], dtype=np.float32))
            emb = np.array(emb_arr, dtype=object)
            # np.savez_compressed auto-appends ``.npz`` when the path
            # doesn't already end in it. Use ``.tmp.npz`` so the rename
            # source actually exists post-save.
            tmp = _STORE_PATH + ".tmp.npz"
            np.savez_compressed(tmp, texts=texts, roles=roles, ts=tss, emb=emb)
            os.replace(tmp, _STORE_PATH)
        except Exception as e:
            log.warning("[semantic_mem] save failed: %s", e)


# ── Singleton ──────────────────────────────────────────────────────── #

_singleton: Optional[SemanticMemory] = None
_singleton_lock = threading.Lock()


def get() -> SemanticMemory:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = SemanticMemory()
        return _singleton


if __name__ == "__main__":
    import sys, tempfile
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Use a temp store so we don't clobber the user's real one.
    tmp = tempfile.NamedTemporaryFile(prefix="aeris_sem_", suffix=".npz",
                                      delete=False)
    tmp.close()
    _STORE_PATH = tmp.name
    sm = SemanticMemory()
    sm.start()
    for role, text in [
        ("user", "let's start pomodoro mode at 7pm every weekday"),
        ("ai",   "got it, scheduling daily 7pm focus blocks"),
        ("user", "what's the weather in delhi right now"),
        ("user", "remind me to email rohan about the design review"),
        ("user", "i need to stop drinking coffee after 4pm"),
    ]:
        sm.add(role, text)
    print("Waiting for embeddings...")
    time.sleep(8)
    print("stats:", sm.stats())
    print("recall 'when did i mention pomodoro?':")
    for score, rec in sm.recall("when did i mention pomodoro?", k=3):
        print(f"  {score:.3f}  [{rec.role}] {rec.text}")
    print()
    print("recall 'caffeine':")
    for score, rec in sm.recall("caffeine", k=3):
        print(f"  {score:.3f}  [{rec.role}] {rec.text}")
    sm.stop()
    try: os.unlink(tmp.name)
    except OSError: pass
