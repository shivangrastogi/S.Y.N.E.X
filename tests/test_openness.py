"""Openness learning (core.openness) — P4. Tmp file + frozen clock."""
from core.openness import OpennessStore


def _store(tmp_path, clock, **kw):
    return OpennessStore(str(tmp_path / "o.json"),
                         now_fn=lambda: clock["t"], **kw)


def test_ema_moves_with_outcomes(tmp_path):
    clock = {"t": 1000.0}
    s = _store(tmp_path, clock)
    assert s.openness("take_break") == 0.6          # start
    s.feedback("take_break", "acted")
    assert s.openness("take_break") > 0.6           # went up
    for _ in range(20):
        s.feedback("take_break", "dismissed")
    assert s.openness("take_break") == 0.15         # floored, never 0


def test_learned_is_none_until_evidence(tmp_path):
    clock = {"t": 1000.0}
    s = _store(tmp_path, clock)
    assert s.learned("battery_low") is None         # keep source default
    s.feedback("battery_low", "acted")
    assert s.learned("battery_low") is not None


def test_settle_converts_stale_pending_to_ignored(tmp_path):
    clock = {"t": 1000.0}
    s = _store(tmp_path, clock, settle_after_s=90)
    s.surfaced("goal_resume")
    assert s.settle() == 0                          # too fresh
    clock["t"] = 1100.0
    assert s.settle() == 1                          # 100s later → ignored
    assert s.stats()["goal_resume"]["ignored"] == 1
    assert s.openness("goal_resume") < 0.6


def test_explicit_feedback_clears_pending(tmp_path):
    clock = {"t": 1000.0}
    s = _store(tmp_path, clock)
    s.surfaced("notif_important")
    s.feedback("notif_important", "acted")
    clock["t"] = 2000.0
    assert s.settle() == 0                          # nothing left to settle


def test_persistence_round_trip(tmp_path):
    clock = {"t": 1000.0}
    s = _store(tmp_path, clock)
    s.feedback("k", "acted")
    v = s.openness("k")
    s2 = _store(tmp_path, clock)
    assert abs(s2.openness("k") - v) < 1e-9
    assert s2.stats()["k"]["acted"] == 1


def test_engine_injects_learned_openness(tmp_path):
    from core.initiative_engine import InitiativeEngine, Initiative

    clock = {"t": 1000.0}
    s = _store(tmp_path, clock)
    for _ in range(10):
        s.feedback("noisy_kind", "dismissed")       # user hates these

    def src():
        return [Initiative(text="x", kind="noisy_kind", openness=0.9,
                           importance=0.9, timeliness=0.9, confidence=0.9,
                           source_id="n1")]

    class NoGate:
        def _in_quiet(self, t):
            return False

    eng = InitiativeEngine(goals_provider=lambda: None,
                           gate_provider=lambda: NoGate(),
                           extra_sources=[src], now_fn=lambda: clock["t"],
                           openness_provider=s.learned)
    out = eng.preview()
    # 0.9*0.9*0.9*0.15 ≈ 0.109 < offer_threshold 0.12 → learned dismissal wins
    assert out == []
