"""Tests for the Memory Fabric (core.memory_fabric).

No encoder, disk, or model — the three stores are injected as in-memory
fakes, so the fabric's federation + hybrid ranking are exercised in pure
Python. See docs/AERIS_AUTONOMOUS_YEAR_PLAN.md (Q1·M1).
"""

import time

from core.memory_fabric import (
    MemoryFabric,
    hybrid_score,
    lexical_sim,
    recency_weight,
)


# ── pure ranking helpers ──────────────────────────────────────────

def test_recency_weight_decays():
    now = 1_000_000.0
    assert recency_weight(now, now) == 1.0
    # one half-life (3 days) → ~0.5
    assert abs(recency_weight(now - 3 * 86400, now) - 0.5) < 1e-6
    assert recency_weight(None, now) == 0.0


def test_lexical_sim_is_query_coverage():
    assert lexical_sim("pomodoro timer", "start the pomodoro timer") == 1.0
    assert lexical_sim("goa trip", "beaches in goa") == 0.5
    assert lexical_sim("", "anything") == 0.0


def test_hybrid_score_weights():
    # all-ones with default weights sums to 1.0
    assert abs(hybrid_score(1.0, 1.0, 1.0) - 1.0) < 1e-9
    # similarity dominates
    assert hybrid_score(1.0, 0.0, 0.0) > hybrid_score(0.0, 1.0, 0.0)


# ── fakes ─────────────────────────────────────────────────────────

class _Rec:
    def __init__(self, text, ts, role="user"):
        self.text, self.ts, self.role = text, ts, role


class FakeSemantic:
    def __init__(self, pairs):
        self._pairs = pairs  # list[(score, _Rec)]
        self.added = []

    def recall(self, query, k=5, min_score=0.0):
        if not query:
            return []  # mirror the real store's empty-query guard
        return sorted(self._pairs, key=lambda p: -p[0])[:k]

    def recent(self, n=40):
        return [(r.ts, r) for _, r in self._pairs][:n]

    def add(self, role, text):
        self.added.append((role, text))


class FakeKG:
    def __init__(self, triples=None, answer=None):
        self._triples = triples or []
        self._answer = answer
        self.statements = []

    def query(self, q):
        return self._answer

    def all_triples(self):
        return self._triples

    def add_statement(self, text, **kw):
        self.statements.append(text)
        return []


class FakeUserMem:
    def __init__(self, data=None):
        self._data = data or {"facts": {}, "notes": [], "preferences": {}}
        self.sets = []
        self.notes_added = []

    def set(self, key, value, source="user_said"):
        self.sets.append((key, value))

    def add_note(self, text):
        self.notes_added.append(text)


def _fabric(sem=None, kg=None, um=None, now=1_000_000.0):
    return MemoryFabric(
        semantic_provider=lambda: sem,
        kg_provider=lambda: kg,
        user_memory_provider=lambda: um,
        now_fn=lambda: now,
    )


# ── recall federation + ranking ───────────────────────────────────

def test_recall_merges_all_sources():
    now = 1_000_000.0
    sem = FakeSemantic([(0.8, _Rec("worked on the flutter app", now - 3600))])
    kg = FakeKG(triples=[{"s": "sara", "p": "is_my", "o": "sister",
                          "raw": "Sara is my sister"}])
    um = FakeUserMem({"facts": {"city": {"value": "Mumbai"}},
                      "notes": [{"text": "buy milk"}], "preferences": {}})
    fab = _fabric(sem, kg, um, now)
    hits = fab.recall("sara", k=6)
    kinds = {h.kind for h in hits}
    assert "semantic" in kinds  # the KG triple matched "sara"
    # every hit carries a routed kind + a score
    assert all(h.kind and h.score >= 0 for h in hits)


def test_fresh_episodic_beats_stale_on_similar_score():
    now = 1_000_000.0
    sem = FakeSemantic([
        (0.70, _Rec("debugging the wake word", now - 60)),          # fresh
        (0.70, _Rec("debugging the wake word", now - 10 * 86400)),  # stale
    ])
    fab = _fabric(sem=sem, now=now)
    hits = fab.recall("wake word", k=2)
    assert hits[0].ts == now - 60  # recency broke the tie


def test_recall_respects_kind_filter():
    now = 1_000_000.0
    sem = FakeSemantic([(0.9, _Rec("some chat", now))])
    kg = FakeKG(triples=[{"raw": "Sara is my sister", "s": "sara"}])
    fab = _fabric(sem, kg, now=now)
    hits = fab.recall("sara", k=6, kinds=["semantic"])
    assert hits and all(h.kind == "semantic" for h in hits)
    assert all(h.source != "semantic_memory" for h in hits)


def test_kg_resolved_answer_ranks_high():
    fab = _fabric(kg=FakeKG(answer="Mumbai"))
    hits = fab.recall("where do I live")
    assert hits[0].text == "Mumbai"
    assert hits[0].meta.get("resolved") is True


def test_recall_survives_missing_stores():
    # No stores wired at all → empty, no crash.
    fab = _fabric()
    assert fab.recall("anything") == []


# ── write routing ─────────────────────────────────────────────────

def test_remember_routes_episodic():
    sem = FakeSemantic([])
    fab = _fabric(sem=sem)
    assert fab.remember("we chatted about lunch", kind="episodic") == "episodic"
    assert sem.added == [("user", "we chatted about lunch")]


def test_remember_auto_detects_fact():
    kg = FakeKG()
    fab = _fabric(kg=kg)
    routed = fab.remember("Sara is my sister", kind="auto")
    assert routed == "semantic"
    assert kg.statements == ["Sara is my sister"]


def test_remember_auto_non_fact_is_episodic():
    sem = FakeSemantic([])
    fab = _fabric(sem=sem)
    assert fab.remember("open chrome and check mail", kind="auto") == "episodic"


def test_remember_note_and_preference():
    um = FakeUserMem()
    fab = _fabric(um=um)
    assert fab.remember("call the plumber", kind="note") == "note"
    assert um.notes_added == ["call the plumber"]
    assert fab.remember("hinglish", kind="preference", subject="language") \
        == "preference"
    assert um.sets == [("language", "hinglish")]


# ── consolidation stub ────────────────────────────────────────────

def test_recall_context_formats_hits():
    now = 1_000_000.0
    sem = FakeSemantic([(0.8, _Rec("worked on the wake word", now))])
    kg = FakeKG(triples=[{"raw": "Sara is my sister", "s": "sara"}])
    fab = _fabric(sem, kg, now=now)
    ctx = fab.recall_context("sara wake", k=6)
    assert ctx.startswith("Relevant memory:")
    assert "Sara is my sister" in ctx


def test_recall_context_empty_when_nothing():
    assert _fabric().recall_context("anything") == ""


def test_consolidate_noop_without_llm():
    fab = _fabric(sem=FakeSemantic([(0.5, _Rec("x", 1.0))]))
    assert fab.consolidate() is None  # no llm → safe no-op


def test_consolidate_writes_note_with_llm():
    now = 1_000_000.0
    sem = FakeSemantic([(0.5, _Rec("coded all evening", now))])
    um = FakeUserMem()
    fab = _fabric(sem=sem, um=um, now=now)
    out = fab.consolidate(llm=lambda prompt: "You coded all evening.")
    assert out == "You coded all evening."
    assert um.notes_added == ["You coded all evening."]
