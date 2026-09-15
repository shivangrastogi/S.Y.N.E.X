"""Tests for core.anticipation — the Anticipation engine (Sentient-Partner Phase 4)."""
from __future__ import annotations

from core.anticipation import Anticipator


def _ant(tmp_path, **kw):
    return Anticipator(path=str(tmp_path / "ant.json"), enabled=True,
                       min_support=3, **kw)


# ── learning + prediction ────────────────────────────────────────────────
def test_learns_and_predicts(tmp_path):
    a = _ant(tmp_path)
    for _ in range(4):
        a.observe("get_time", "gmail kholo", "open_app", "morning")
    preds = a.predict("morning", "get_time")
    assert preds and preds[0][0] == "gmail kholo"
    assert preds[0][1] == "open_app"
    assert preds[0][2] == 1.0                       # 4/4


def test_min_support_gates(tmp_path):
    a = _ant(tmp_path)
    a.observe("get_time", "gmail kholo", "open_app", "morning")   # only 1
    assert a.predict("morning", "get_time") == []


def test_time_of_day_prior_fallback(tmp_path):
    a = _ant(tmp_path)
    for _ in range(4):
        a.observe("get_time", "coffee timer", "quick_timer", "morning")
    # unseen predecessor → falls back to the morning|* prior
    preds = a.predict("morning", "some_unseen_intent")
    assert preds and preds[0][0] == "coffee timer"


# ── trust-gated suggestions ──────────────────────────────────────────────
def test_suggest_auto_high_conf_is_do(tmp_path):
    a = _ant(tmp_path)
    for _ in range(5):
        a.observe("get_time", "gmail kholo", "open_app", "morning")
    s = a.suggest("morning", "get_time")
    assert s is not None
    assert s.trust == "auto" and s.action == "do"
    assert "gmail kholo" in s.phrase


def test_suggest_offer_for_stateful(tmp_path):
    a = _ant(tmp_path)
    for _ in range(5):
        a.observe("open_app", "add task standup", "add_task", "morning")
    s = a.suggest("morning", "open_app")
    assert s is not None
    assert s.trust == "offer" and s.action == "offer"
    assert s.phrase.endswith("karoon?")


def test_confirm_and_forbid_never_anticipated(tmp_path):
    a = _ant(tmp_path)
    for _ in range(5):
        a.observe("open_app", "message rohan", "send_whatsapp", "evening")
    assert a.suggest("evening", "open_app") is None     # outward → confirm → not anticipated
    b = _ant(tmp_path)
    for _ in range(5):
        b.observe("night", "shutdown karo", "shutdown_pc", "night")
    assert b.suggest("night", "night") is None          # forbidden → not anticipated


def test_low_confidence_stays_quiet(tmp_path):
    a = _ant(tmp_path)
    # three equally-likely next commands → top conf ~0.33 < MED (0.35)
    for cmd in ("open_app a", "open_app b", "open_app c"):
        a.observe("get_time", cmd, "open_app", "morning")
        a.observe("get_time", cmd, "open_app", "morning")
    assert a.suggest("morning", "get_time") is None


# ── kill switch + persistence ────────────────────────────────────────────
def test_disabled_is_inert(tmp_path):
    a = _ant(tmp_path)
    a.enabled = False
    a.observe("get_time", "gmail kholo", "open_app", "morning")
    assert a.predict("morning", "get_time") == []
    assert a.suggest("morning", "get_time") is None


def test_persist_round_trip(tmp_path):
    p = str(tmp_path / "ant.json")
    a = Anticipator(path=p, enabled=True, min_support=3)
    for _ in range(4):
        a.observe("get_time", "gmail kholo", "open_app", "morning")
    a.persist()
    b = Anticipator(path=p, enabled=True, min_support=3)
    preds = b.predict("morning", "get_time")
    assert preds and preds[0][0] == "gmail kholo" and preds[0][1] == "open_app"
