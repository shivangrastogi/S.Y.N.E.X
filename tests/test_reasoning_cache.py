"""Tests for core.reasoning_cache — stable-reply memoization (issue #7).
The critical property under test: it must NEVER cache a live-state query."""
from __future__ import annotations

from core.reasoning_cache import ReasoningCache, is_cacheable


def _rc(tmp_path, **kw):
    return ReasoningCache(path=str(tmp_path / "rc.json"), enabled=True, **kw)


# ── the safety gate (the whole point) ────────────────────────────────────
def test_stateful_queries_are_never_cacheable():
    for q in ("abhi time kya hai", "battery kitni bachi hai", "aaj mausam kaisa hai",
              "konsi file sabse badi hai", "downloads me kya hai", "stock price kya hai"):
        assert is_cacheable(q) is False


def test_stable_queries_are_cacheable():
    for q in ("recursion kya hota hai", "explain gravity", "python me list kya hai"):
        assert is_cacheable(q) is True


def test_trivial_one_word_not_cacheable():
    assert is_cacheable("hello") is False


def test_put_refuses_stateful_query(tmp_path):
    rc = _rc(tmp_path)
    rc.put("abhi time kya hai", "3 baje hain", now=1000.0)
    assert rc.get("abhi time kya hai", now=1000.0) is None      # never stored


# ── round-trip + normalization ───────────────────────────────────────────
def test_round_trip_and_normalization(tmp_path):
    rc = _rc(tmp_path)
    rc.put("Recursion kya hota hai?", "Jab function khud ko call kare.", now=1000.0)
    # different casing / trailing punctuation / spacing → same key
    assert rc.get("  recursion   kya hota hai  ", now=1001.0) == "Jab function khud ko call kare."


# ── TTL + LRU + kill switch ──────────────────────────────────────────────
def test_ttl_expiry(tmp_path):
    rc = _rc(tmp_path, ttl_s=100.0)
    rc.put("explain gravity", "Mass attracts mass.", now=1000.0)
    assert rc.get("explain gravity", now=1050.0) == "Mass attracts mass."
    assert rc.get("explain gravity", now=1200.0) is None        # past TTL


def test_lru_eviction(tmp_path):
    rc = _rc(tmp_path, max_entries=2)
    rc.put("explain one thing", "a", now=1.0)
    rc.put("explain two things", "b", now=2.0)
    rc.get("explain one thing", now=3.0)                        # touch → most-recent
    rc.put("explain three things", "c", now=4.0)                # evicts "two"
    assert rc.get("explain one thing", now=5.0) == "a"
    assert rc.get("explain two things", now=5.0) is None
    assert rc.get("explain three things", now=5.0) == "c"


def test_disabled_is_inert(tmp_path):
    rc = ReasoningCache(path=str(tmp_path / "rc.json"), enabled=False)
    rc.put("recursion kya hota hai", "x", now=1.0)
    assert rc.get("recursion kya hota hai", now=1.0) is None


def test_persist_round_trip(tmp_path):
    p = str(tmp_path / "rc.json")
    a = ReasoningCache(path=p, enabled=True)
    a.put("explain gravity", "Mass attracts mass.", now=1000.0)
    a.persist()
    b = ReasoningCache(path=p, enabled=True)
    assert b.get("explain gravity", now=1000.0) == "Mass attracts mass."
