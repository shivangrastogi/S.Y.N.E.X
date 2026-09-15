"""Memory Fabric — one ranked recall surface over AERIS's existing stores.

Q1·M1 of the Autonomous-Year plan (see docs/AERIS_AUTONOMOUS_YEAR_PLAN.md).
This is a *unifying* layer, not a new store: it federates the three memories
AERIS already keeps and returns a single, typed, hybrid-ranked result set the
agent runtime (planner / initiative engine) can reason over.

Federated sources
-----------------
* **Episodic** — `core.semantic_memory` (embedding-backed conversation log,
  cosine top-k). This gives the fabric real semantic similarity for free.
* **Semantic** — `core.kg_memory` (subject/predicate/object triples the user
  dictated: "Sara is my sister").
* **Preference / fact / note** — `core.memory.UserMemory`
  (`data/user_memory.json`).

Hybrid ranking
--------------
Each hit gets ``final = w_sim·similarity + w_recency·recency + w_salience·salience``.
Episodic hits bring a true cosine ``similarity``; keyword-matched KG/user hits
use a lexical overlap as a similarity proxy. Recency is an exponential decay on
record age. This is why "what was I working on yesterday evening?" beats a
stale but lexically-similar note.

Testability
-----------
The three stores are injected (``configure`` / constructor providers), so the
whole fabric unit-tests with in-memory fakes — no encoder, no disk, no model.
The engine wires the *live* singletons at boot via ``configure(...)`` so reads
and writes stay consistent with the rest of AERIS.
"""
from __future__ import annotations

import logging
import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ranking weights + recency half-life. Tunable; kept here so the eval harness
# (Q1 gate) can sweep them.
_W_SIM = 0.6
_W_RECENCY = 0.25
_W_SALIENCE = 0.15
_RECENCY_HALFLIFE_DAYS = 3.0

VALID_KINDS = ("episodic", "semantic", "preference", "note", "fact", "goal")

# Goals outrank notes and facts on purpose. A standing intention is the most
# actionable thing AERIS can know while planning — "book the Delhi flight,
# blocked on which airline" changes what the planner should do in a way that a
# lexically-similar old note does not.
_GOAL_SALIENCE = 0.85


# ── result type ─────────────────────────────────────────────────────── #

@dataclass
class MemoryHit:
    kind: str          # one of VALID_KINDS
    text: str          # human-readable content
    score: float       # final hybrid rank (higher = better)
    similarity: float = 0.0
    recency: float = 0.0
    salience: float = 0.5
    subject: Optional[str] = None
    ts: Optional[float] = None
    source: str = ""   # which store it came from
    meta: dict = field(default_factory=dict)


# ── pure ranking helpers (unit-tested in isolation) ─────────────────── #

def recency_weight(ts: Optional[float], now: float,
                   halflife_days: float = _RECENCY_HALFLIFE_DAYS) -> float:
    """Exponential decay in [0, 1]; 1.0 for 'now', 0.5 after one half-life."""
    if not ts:
        return 0.0
    age_days = max(0.0, (now - ts) / 86400.0)
    return math.pow(0.5, age_days / max(halflife_days, 1e-6))


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Words that carry no topic. Without this, "what is the weather" and "book the
# delhi flight" overlap on "the" and score 0.25 — enough, once multiplied by a
# goal's salience, to push a completely unrelated standing intention into a
# planner's context. A shared stopword is not a match.
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "am", "of", "to",
    "for", "in", "on", "at", "by", "with", "and", "or", "but", "if", "then",
    "this", "that", "these", "those", "it", "its", "my", "me", "i", "you",
    "your", "he", "she", "they", "we", "what", "which", "who", "how", "when",
    "where", "why", "do", "does", "did", "can", "could", "would", "will",
    "should", "please", "kya", "hai", "ho", "ka", "ki", "ke", "ko", "se",
    "me", "mera", "meri", "mujhe", "ye", "yeh", "wo", "woh", "aur", "karo",
    "kar", "na", "ab", "bhi", "tha", "thi",
})


def _content(text: str) -> set:
    return {t for t in _TOKEN_RE.findall((text or "").lower())
            if t not in _STOPWORDS}


def lexical_sim(query: str, text: str) -> float:
    """Cheap overlap score in [0, 1] for stores without embeddings.

    Stopword-filtered on both sides: a query made only of stopwords has
    nothing to match on and scores 0 rather than matching everything.
    """
    q = _content(query)
    t = _content(text)
    if not q or not t:
        return 0.0
    inter = len(q & t)
    if inter == 0:
        return 0.0
    # Recall-biased: how much of the query is covered by the text.
    return inter / len(q)


def hybrid_score(similarity: float, recency: float, salience: float,
                 *, w_sim: float = _W_SIM, w_recency: float = _W_RECENCY,
                 w_salience: float = _W_SALIENCE) -> float:
    return (w_sim * similarity + w_recency * recency + w_salience * salience)


# ── the fabric ──────────────────────────────────────────────────────── #

class MemoryFabric:
    """Federated, hybrid-ranked recall over the existing memory stores.

    Providers are zero-arg callables returning a store (or None). Defaults
    lazily borrow the real singletons; tests inject fakes.
    """

    def __init__(self,
                 *,
                 semantic_provider: Optional[Callable[[], Any]] = None,
                 kg_provider: Optional[Callable[[], Any]] = None,
                 user_memory_provider: Optional[Callable[[], Any]] = None,
                 goal_provider: Optional[Callable[[], Any]] = None,
                 now_fn: Callable[[], float] = time.time):
        self._sem_provider = semantic_provider or _default_semantic
        self._kg_provider = kg_provider or _default_kg
        self._um_provider = user_memory_provider or _default_user_memory
        self._goal_provider = goal_provider or _default_goals
        self._now = now_fn

    # -- write path -----------------------------------------------------

    def remember(self, text: str, *, kind: str = "auto",
                 subject: Optional[str] = None, role: str = "user") -> str:
        """Persist a memory into the right store. Returns the routed kind."""
        text = (text or "").strip()
        if not text:
            return "ignored"
        routed = kind
        if kind == "auto":
            routed = "semantic" if _looks_like_fact(text) else "episodic"
        try:
            if routed == "episodic":
                sem = self._sem_provider()
                if sem is not None:
                    sem.add(role, text)
            elif routed == "semantic":
                kg = self._kg_provider()
                if kg is not None:
                    kg.add_statement(text)
            elif routed in ("preference", "fact"):
                um = self._um_provider()
                if um is not None and subject:
                    um.set(subject, text)
            elif routed == "note":
                um = self._um_provider()
                if um is not None:
                    um.add_note(text)
        except Exception as e:  # a store hiccup must never crash a turn
            log.warning("[fabric] remember(%s) failed: %s", routed, e)
            return "error"
        return routed

    # -- read path ------------------------------------------------------

    def recall(self, query: str, k: int = 6,
               kinds: Optional[Iterable[str]] = None) -> list[MemoryHit]:
        """Top-k typed memories, hybrid-ranked across all stores."""
        query = (query or "").strip()
        if not query:
            return []
        want = set(kinds) if kinds else None
        now = self._now()
        hits: list[MemoryHit] = []
        if want is None or "episodic" in want:
            hits.extend(self._recall_episodic(query, k, now))
        if want is None or "semantic" in want:
            hits.extend(self._recall_semantic(query, now))
        if want is None or (want & {"preference", "note", "fact"}):
            hits.extend(self._recall_user(query, now, want))
        if want is None or "goal" in want:
            hits.extend(self._recall_goals(query, now))
        hits.sort(key=lambda h: -h.score)
        return hits[:k]

    def _recall_goals(self, query: str, now: float) -> list[MemoryHit]:
        """Standing intentions relevant to this query.

        **Only open goals.** A done or dropped goal must never reach a planner
        — injecting one is how an agent cheerfully re-books a flight the user
        already booked. `Goal.is_open()` is the gate.

        Like the KG and user-memory sources, this is lexically gated: a goal
        that has nothing to do with the query stays out. Surfacing *all* open
        goals on every turn is a different question ("what is the user working
        on?") and a different answer — it would push unrelated intentions into
        every plan, which is exactly the context bloat the ≤12-tool menu exists
        to avoid for an embedded 1.5B model.
        """
        store = self._safe(self._goal_provider)
        if store is None:
            return []
        try:
            goals = store.open_goals()
        except Exception as e:
            log.debug("[fabric] goal recall failed: %s", e)
            return []
        out: list[MemoryHit] = []
        for g in goals or []:
            try:
                text = getattr(g, "text", "") or ""
                if not text:
                    continue
                sim = lexical_sim(query, text)
                if sim <= 0.0:
                    continue
                ts = getattr(g, "updated", None) or getattr(g, "created", None)
                rec = recency_weight(ts, now)
                out.append(MemoryHit(
                    kind="goal", text=_goal_line(g), similarity=sim,
                    recency=rec, salience=_GOAL_SALIENCE,
                    score=hybrid_score(sim, rec, _GOAL_SALIENCE),
                    subject=getattr(g, "id", None), ts=ts, source="goal_system",
                    meta={"state": getattr(g, "state", ""),
                          "blocker": getattr(g, "blocker", "") or ""}))
            except Exception as e:   # one malformed goal must not lose the rest
                log.debug("[fabric] skipping goal %r: %s", g, e)
        return out

    def _recall_episodic(self, query: str, k: int, now: float) -> list[MemoryHit]:
        sem = self._safe(self._sem_provider)
        if sem is None:
            return []
        try:
            pairs = sem.recall(query, k=max(k, 8))
        except Exception as e:
            log.debug("[fabric] semantic recall failed: %s", e)
            return []
        out: list[MemoryHit] = []
        for score, rec in pairs:
            ts = getattr(rec, "ts", None)
            rq = recency_weight(ts, now)
            out.append(MemoryHit(
                kind="episodic", text=getattr(rec, "text", ""),
                similarity=float(score), recency=rq, salience=0.5,
                score=hybrid_score(float(score), rq, 0.5),
                ts=ts, source="semantic_memory",
                meta={"role": getattr(rec, "role", "")}))
        return out

    def _recall_semantic(self, query: str, now: float) -> list[MemoryHit]:
        kg = self._safe(self._kg_provider)
        if kg is None:
            return []
        out: list[MemoryHit] = []
        # Direct question answer, if the KG can resolve one.
        try:
            ans = kg.query(query)
            if ans:
                sim = 0.9  # a resolved KG answer is a strong, exact match
                out.append(MemoryHit(
                    kind="semantic", text=str(ans), similarity=sim,
                    recency=0.0, salience=0.7,
                    score=hybrid_score(sim, 0.0, 0.7),
                    source="kg_memory", meta={"resolved": True}))
        except Exception:
            pass
        # Lexically-matched triples for breadth.
        try:
            triples = kg.all_triples()
        except Exception:
            triples = []
        for t in triples or []:
            raw = t.get("raw") or f"{t.get('s','')} {t.get('p','')} {t.get('o','')}"
            sim = lexical_sim(query, raw)
            if sim <= 0.0:
                continue
            out.append(MemoryHit(
                kind="semantic", text=raw.strip(), similarity=sim,
                recency=0.0, salience=0.6,
                score=hybrid_score(sim, 0.0, 0.6),
                subject=t.get("s"), source="kg_memory", meta=dict(t)))
        return out

    def _recall_user(self, query: str, now: float,
                     want: Optional[set]) -> list[MemoryHit]:
        um = self._safe(self._um_provider)
        if um is None:
            return []
        data = getattr(um, "_data", None) or {}
        out: list[MemoryHit] = []
        # Facts + preferences (dict of key -> value|entry).
        for bucket, kind in (("facts", "fact"), ("preferences", "preference")):
            if want and kind not in want:
                continue
            for key, val in (data.get(bucket) or {}).items():
                value = val.get("value") if isinstance(val, dict) else val
                text = f"{key}: {value}"
                sim = max(lexical_sim(query, key), lexical_sim(query, str(value)))
                if sim <= 0.0:
                    continue
                out.append(MemoryHit(
                    kind=kind, text=text, similarity=sim, recency=0.0,
                    salience=0.65, score=hybrid_score(sim, 0.0, 0.65),
                    subject=key, source="user_memory"))
        # Free-text notes.
        if not want or "note" in want:
            for note in (data.get("notes") or []):
                text = note.get("text") if isinstance(note, dict) else str(note)
                sim = lexical_sim(query, text or "")
                if sim <= 0.0:
                    continue
                out.append(MemoryHit(
                    kind="note", text=text or "", similarity=sim, recency=0.0,
                    salience=0.5, score=hybrid_score(sim, 0.0, 0.5),
                    source="user_memory"))
        return out

    def recall_context(self, query: str, k: int = 4,
                       kinds: Optional[Iterable[str]] = None) -> str:
        """A compact 'Relevant memory:' block for a planner/agent prompt, or ''
        when nothing relevant is found. This is how the agent gets continuity —
        it recalls what it knows about the goal before planning."""
        hits = self.recall(query, k=k, kinds=kinds)
        if not hits:
            return ""
        lines = "\n".join(f"- {h.text}" for h in hits)
        return "Relevant memory:\n" + lines

    # -- consolidation (stub matured in later milestones) --------------

    def consolidate(self, llm: Optional[Callable[[str], str]] = None,
                    *, max_recent: int = 40) -> Optional[str]:
        """Summarize recent episodic memory into a durable note — the agent's
        "sleep". No-op (returns None) when no summarizer is available, so it's
        safe to schedule now and give it a real LLM later (Q1 nightly job)."""
        if llm is None:
            return None
        sem = self._safe(self._sem_provider)
        if sem is None:
            return None
        try:
            # Prefer the dedicated tail accessor; fall back for older stores.
            if hasattr(sem, "recent"):
                recent = sem.recent(max_recent)
            else:
                recent = sem.recall("", k=max_recent)
        except Exception:
            recent = []
        if not recent:
            return None
        blob = "\n".join(getattr(r, "text", "") for _, r in recent)
        try:
            summary = llm(
                "In 2 lines, summarise what the user did/said. Hinglish:\n" + blob)
        except Exception as e:
            log.warning("[fabric] consolidate llm failed: %s", e)
            return None
        if summary:
            self.remember(summary.strip(), kind="note")
        return summary

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _safe(provider: Callable[[], Any]) -> Any:
        try:
            return provider()
        except Exception as e:
            log.debug("[fabric] provider unavailable: %s", e)
            return None


# ── fact heuristic (routes remember(auto=)) ─────────────────────────── #

_FACT_RE = re.compile(
    r"\b(is|are|was|were|hai|ka naam|lives? in|rehta|works? at|"
    r"my|mera|meri|number is|birthday)\b", re.I)


def _goal_line(g: Any) -> str:
    """One line a planner can act on.

    The state and the blocker are the actionable half — "blocked (need_user):
    which airline?" tells the model both what is wanted *and* why it stalled,
    which is the difference between re-planning usefully and re-planning into
    the same wall.
    """
    text = getattr(g, "text", "") or ""
    state = getattr(g, "state", "") or ""
    bits = []
    if state and state != "captured":
        blocker = getattr(g, "blocker", None)
        bits.append(f"{state} ({blocker})" if blocker else state)
    ask = (getattr(g, "ask", None) or "").strip()
    if ask:
        bits.append(f"waiting on: {ask}")
    suffix = f" [{'; '.join(bits)}]" if bits else ""
    return f"ongoing goal: {text}{suffix}"


def _looks_like_fact(text: str) -> bool:
    return bool(_FACT_RE.search(text or ""))


# ── default providers (lazy, borrow live singletons) ────────────────── #

def _default_semantic() -> Any:
    from core import semantic_memory
    return semantic_memory.get()


def _default_kg() -> Any:
    from core.kg_memory import get_kg
    return get_kg()


def _default_goals() -> Any:
    from core.goal_system import get_goal_store
    return get_goal_store()


_um_singleton = None


def _default_user_memory() -> Any:
    global _um_singleton
    if _um_singleton is not None:
        return _um_singleton
    from core.memory import UserMemory
    _um_singleton = UserMemory(os.path.join(_ROOT, "data", "user_memory.json"))
    return _um_singleton


# ── module singleton + engine wiring ────────────────────────────────── #

_FABRIC: Optional[MemoryFabric] = None


def get_fabric() -> MemoryFabric:
    global _FABRIC
    if _FABRIC is None:
        _FABRIC = MemoryFabric()
    return _FABRIC


def configure(*, semantic=None, kg=None, user_memory=None,
              goals=None) -> MemoryFabric:
    """Wire the fabric to the engine's LIVE store singletons at boot, so reads
    and writes stay consistent with the rest of AERIS.

    Omitted stores fall back to their lazy default provider, so an existing
    caller that passes only the original three keeps working and still picks
    up the goal store.
    """
    global _FABRIC
    _FABRIC = MemoryFabric(
        semantic_provider=(lambda: semantic) if semantic is not None else None,
        kg_provider=(lambda: kg) if kg is not None else None,
        user_memory_provider=(lambda: user_memory) if user_memory is not None else None,
        goal_provider=(lambda: goals) if goals is not None else None,
    )
    return _FABRIC
