"""Trust dashboard CONTROLS — grant persistence (core.autonomy) + the pure
apply_action layer (core.trust_view). Real gate on a tmp grants file, injected
panic path; no HTTP server, browser, or model.
"""
import json

from core.autonomy import TrustGate, Ledger, DEFAULT_GRANTS, set_panic
from core import trust_view as tv


def _gate(tmp_path):
    return TrustGate(ledger=Ledger(str(tmp_path / "l.jsonl")),
                     grants_path=str(tmp_path / "grants.json"))


# ── grant persistence + HARD_CAP ceiling ──────────────────────────────

def test_set_grant_persists_and_reloads(tmp_path):
    g = _gate(tmp_path)
    assert g.granted_level("message") == 2          # default L2
    g.set_grant("message", 3)                        # raise to L3
    assert g.granted_level("message") == 3
    # a fresh gate on the same file reloads the override
    g2 = TrustGate(ledger=Ledger(str(tmp_path / "l2.jsonl")),
                   grants_path=str(tmp_path / "grants.json"))
    assert g2.granted_level("message") == 3
    # only the override is persisted, not the whole default table
    saved = json.loads((tmp_path / "grants.json").read_text())
    assert saved["grants"] == {"message": 3}


def test_set_grant_cannot_exceed_hard_cap(tmp_path):
    g = _gate(tmp_path)
    eff = g.set_grant("payment", 5)                  # try to max out payment
    assert eff == 2                                  # HARD_CAP L2 wins
    assert g.grants["payment"] == 2                  # raw grant clamped too
    eff2 = g.set_grant("destructive", 4)
    assert eff2 == 2


def test_set_grant_floor_and_unknown_class(tmp_path):
    g = _gate(tmp_path)
    assert g.set_grant("device", -3) == 0            # clamped up to L0
    try:
        g.set_grant("nonsense", 2)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_grants_are_in_memory_without_a_path(tmp_path):
    # No grants_path → set_grant works but nothing is written.
    g = TrustGate(ledger=Ledger(str(tmp_path / "l.jsonl")))
    g.set_grant("web", 3)
    assert g.granted_level("web") == 3
    assert not (tmp_path / "grants.json").exists()


# ── apply_action (the dashboard control surface) ──────────────────────

def test_apply_action_grant(tmp_path):
    g = _gate(tmp_path)
    res = tv.apply_action("grant", {"cls": "call", "level": 3}, gate=g)
    assert res["ok"] and res["granted"] == 3
    assert g.granted_level("call") == 3


def test_apply_action_grant_respects_cap(tmp_path):
    g = _gate(tmp_path)
    res = tv.apply_action("grant", {"cls": "payment", "level": 5}, gate=g)
    assert res["granted"] == 2                        # capped, never autonomous


def test_apply_action_quiet(tmp_path):
    g = _gate(tmp_path)
    res = tv.apply_action("quiet", {"start": 22, "end": 6}, gate=g)
    assert res["quiet_hours"] == {"start": 22, "end": 6}
    assert g.budgets.quiet_start_h == 22 and g.budgets.quiet_end_h == 6


def test_apply_action_panic_toggles_flag(tmp_path):
    g = _gate(tmp_path)
    ppath = str(tmp_path / "panic.flag")
    tv.apply_action("panic", {"on": True}, gate=g, panic_path=ppath)
    import os
    assert os.path.exists(ppath)
    tv.apply_action("panic", {"on": False}, gate=g, panic_path=ppath)
    assert not os.path.exists(ppath)


def test_apply_action_bad_requests_raise(tmp_path):
    g = _gate(tmp_path)
    for action, params in [("grant", {"cls": "call"}),      # no level
                           ("nonsense", {})]:
        try:
            tv.apply_action(action, params, gate=g)
            assert False, f"{action} should have raised"
        except ValueError:
            pass
