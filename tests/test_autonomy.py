"""Tests for the Autonomy Ladder + Ledger (core.autonomy). Injectable clock +
tmp ledger, no disk beyond tmp_path. See docs/AERIS_AUTONOMOUS_YEAR_PLAN.md M3.
"""

from datetime import datetime

from core.autonomy import (
    Budgets,
    Decision,
    Ledger,
    TrustGate,
    classify,
    L0_ASK,
    L1_SUGGEST,
    L2_DRAFT,
    L3_ACT,
    L4_GOAL,
)


# ── classification ────────────────────────────────────────────────

def test_classify():
    assert classify("torch_on") == "device"
    assert classify("send_whatsapp") == "message"
    assert classify("call_contact") == "call"
    assert classify("upi_pay") == "payment"
    assert classify("shutdown_pc") == "system"
    assert classify("kg_forget") == "destructive"   # via confirm_gate list
    assert classify("delete_note") == "destructive"
    assert classify("open_app") == "app"
    assert classify("get_weather") == "read"


# ── ladder grants ─────────────────────────────────────────────────

def _gate(tmp_path, now=None, grants=None, budgets=None, panic=False):
    led = Ledger(str(tmp_path / "ledger.jsonl"),
                 now_fn=(lambda: now) if now else __import__("time").time)
    return TrustGate(ledger=led, grants=grants, budgets=budgets,
                     now_fn=(lambda: now) if now else __import__("time").time,
                     is_panic=lambda: panic)


def test_reversible_device_acts_freely(tmp_path):
    g = _gate(tmp_path, now=_noon())
    d = g.authorize("torch_on", L3_ACT)
    assert d.outcome == "allow" and d.cls == "device"


def test_message_needs_confirm_above_grant(tmp_path):
    g = _gate(tmp_path, now=_noon())
    # message granted L2; an L3 autonomous send must ask
    d = g.authorize("send_whatsapp", L3_ACT)
    assert d.outcome == "confirm"
    # at L2 it's allowed (draft/one-tap)
    assert g.authorize("send_whatsapp", L2_DRAFT).outcome == "allow"


def test_payment_never_autonomous(tmp_path):
    g = _gate(tmp_path, now=_noon())
    assert g.authorize("upi_pay", L3_ACT).outcome == "deny"
    # even L1 offer isn't an autonomous act; L0 grant → L1 request denied
    assert g.authorize("upi_pay", L1_SUGGEST).outcome == "deny"


def test_destructive_hard_capped(tmp_path):
    # even if the user over-grants destructive to L4, HARD_CAP holds it at L2
    g = _gate(tmp_path, now=_noon(), grants={"destructive": L4_GOAL})
    assert g.granted_level("destructive") == L2_DRAFT
    assert g.authorize("kg_forget", L3_ACT).outcome == "confirm"


# ── budgets ───────────────────────────────────────────────────────

def test_spend_cap_triggers_confirm(tmp_path):
    now = _noon()
    g = _gate(tmp_path, now=now, budgets=Budgets(spend_cap_day=1000))
    g.ledger.record(action="upi_pay", args={}, cls="payment", level=2,
                    decision="allow", why="x", cost=900)
    d = g.authorize("upi_pay", L2_DRAFT, cost=200)
    assert d.outcome == "confirm" and "spend cap" in d.why


def test_rate_cap_triggers_confirm(tmp_path):
    now = _noon()
    g = _gate(tmp_path, now=now, budgets=Budgets(rate_cap_day={"message": 2}))
    for _ in range(2):
        g.ledger.record(action="send_whatsapp", args={}, cls="message",
                        level=2, decision="allow", why="x")
    assert g.authorize("send_whatsapp", L2_DRAFT).outcome == "confirm"


def test_quiet_hours_blocks_proactive_act(tmp_path):
    g = _gate(tmp_path, now=_at_hour(2))  # 2am, in quiet window
    assert g.authorize("torch_on", L3_ACT).outcome == "confirm"
    # daytime it acts
    assert _gate(tmp_path, now=_at_hour(14)).authorize(
        "torch_on", L3_ACT).outcome == "allow"


# ── panic ─────────────────────────────────────────────────────────

def test_panic_denies_everything(tmp_path):
    g = _gate(tmp_path, now=_noon(), panic=True)
    assert g.authorize("torch_on", L3_ACT).outcome == "deny"
    assert g.authorize("get_weather", L3_ACT).outcome == "deny"


# ── ledger ────────────────────────────────────────────────────────

def test_ledger_records_and_explains(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.record(action="silence_phone", args={}, cls="device", level=3,
               decision="allow", why="meeting started, you always DND")
    assert led.recent(1)[0]["action"] == "silence_phone"
    assert "DND" in led.explain("silence_phone")
    assert led.explain("nope") is None


def test_ledger_persists(tmp_path):
    path = str(tmp_path / "l.jsonl")
    Ledger(path).record(action="a", args={}, cls="read", level=3,
                        decision="allow", why="w")
    assert Ledger(path).all()[0]["action"] == "a"


def test_ledger_first_record_is_not_double_counted(tmp_path):
    # Regression: on a fresh ledger whose FIRST op is record(), the lazy cache
    # load once read the just-written entry back and appended it twice.
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.record(action="a", args={}, cls="read", level=3, decision="allow", why="w")
    assert len(led.all()) == 1
    led.record(action="b", args={}, cls="read", level=3, decision="allow", why="w")
    assert [e["action"] for e in led.all()] == ["a", "b"]
    # and the on-disk file agrees (no phantom duplicate line)
    assert len(Ledger(str(tmp_path / "l.jsonl")).all()) == 2


# ── helpers ───────────────────────────────────────────────────────

def _noon():
    return datetime(2026, 7, 12, 12, 0).timestamp()


def _at_hour(h):
    return datetime(2026, 7, 12, h, 0).timestamp()
