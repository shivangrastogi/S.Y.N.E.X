"""Trust view (core.trust_view) — the read-only audit/grants surface for the
Mind dashboard. Real TrustGate + Ledger on a tmp file, injected clock; no
dashboard, server, or model.
"""
from datetime import datetime

from core.autonomy import (Ledger, TrustGate, classify, set_panic,
                           L2_DRAFT, L3_ACT)
from core import trust_view as tv


def _at(h):
    return datetime(2026, 7, 12, h, 0).timestamp()


def _wire(tmp_path, *, hour=12, panic_path=None):
    led = Ledger(str(tmp_path / "ledger.jsonl"), now_fn=lambda: _at(hour))
    is_panic = (lambda: False) if panic_path is None else \
        (lambda: __import__("os").path.exists(panic_path))
    gate = TrustGate(ledger=led, now_fn=lambda: _at(hour), is_panic=is_panic)
    return gate, led


def _log(led, action, decision, result="ok"):
    led.record(action=action, args={}, cls=classify(action), level=L3_ACT,
               decision=decision, why="test", result=result)


# ── grants + hard cap ─────────────────────────────────────────────────

def test_grants_view_sorted_and_surfaces_hard_cap(tmp_path):
    gate, _ = _wire(tmp_path)
    rows = tv.grants_view(gate)
    by_cls = {r["cls"]: r for r in rows}

    # payment is L0 and can never go autonomous
    assert by_cls["payment"]["granted"] == 0
    assert by_cls["payment"]["granted_name"] == "Ask"
    # device is a reversible L3 act-and-notify
    assert by_cls["device"]["granted"] == 3
    assert "reversible" in by_cls["device"]["blurb"]
    # most-trusted first
    assert rows[0]["granted"] >= rows[-1]["granted"]


def test_hard_cap_flagged_when_it_bites(tmp_path):
    # grant destructive an over-cap L4 → HARD_CAP pulls the effective level down
    led = Ledger(str(tmp_path / "l.jsonl"))
    gate = TrustGate(ledger=led, grants={"destructive": 4})
    row = next(r for r in tv.grants_view(gate) if r["cls"] == "destructive")
    assert row["raw_grant"] == 4
    assert row["granted"] == 2               # capped to L2
    assert row["capped"] is True
    assert row["hard_cap"] == 2


# ── audit trail ───────────────────────────────────────────────────────

def test_audit_is_newest_first_with_reasons(tmp_path):
    gate, led = _wire(tmp_path)
    _log(led, "torch_on", "allow", "lit")
    _log(led, "upi_pay", "deny", "BLOCKED")
    rows = tv.audit_view(gate, n=10)
    assert rows[0]["action"] == "upi_pay"    # newest first
    assert rows[0]["decision"] == "deny"
    assert rows[0]["cls"] == "payment"
    assert rows[1]["action"] == "torch_on"
    assert rows[0]["time"] == "12:00"


def test_audit_respects_limit(tmp_path):
    gate, led = _wire(tmp_path)
    for i in range(30):
        _log(led, f"act_{i}", "allow")
    assert len(tv.audit_view(gate, n=5)) == 5


# ── state + stats ─────────────────────────────────────────────────────

def test_snapshot_state_and_decision_stats(tmp_path):
    gate, led = _wire(tmp_path, hour=12)
    _log(led, "torch_on", "allow")
    _log(led, "send_message", "confirm")
    _log(led, "upi_pay", "deny")
    snap = tv.snapshot(gate)
    assert snap["panic"] is False
    assert snap["quiet_hours"]["active"] is False       # noon
    assert snap["stats"] == {"allow": 1, "confirm": 1, "deny": 1}
    assert snap["grants"] and snap["audit"]


def test_snapshot_quiet_hours_active_at_night(tmp_path):
    gate, _ = _wire(tmp_path, hour=2)                    # 02:00, inside 23–07
    assert tv.snapshot(gate)["quiet_hours"]["active"] is True


def test_snapshot_reflects_panic(tmp_path):
    ppath = str(tmp_path / "panic.flag")
    gate, _ = _wire(tmp_path, panic_path=ppath)
    assert tv.snapshot(gate)["panic"] is False
    set_panic(True, path=ppath)
    try:
        assert tv.snapshot(gate)["panic"] is True
    finally:
        set_panic(False, path=ppath)
