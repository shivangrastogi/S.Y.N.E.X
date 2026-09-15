"""Routine offers — the learning-loop bridge between the learner (suggests) and
the graduation tracker (decides auto-run trust). Fake learner + tmp tracker, no
camera/disk/model. See core/routine_offers.py.
"""
from core.routine_learner import Suggestion
from core.routine_graduation import GraduationTracker
from core import routine_offers as ro


def _sugg(key, *, actions=None, conf=0.8):
    return Suggestion(
        key=key, title=f"offer {key}", detail="because pattern",
        confidence=conf, evidence_days=5,
        routine_spec={"name": key, "enabled": False,
                      "actions": actions or [{"kind": "notify", "params": {}}]},
    )


def _tracker(tmp_path, threshold=3):
    return GraduationTracker(str(tmp_path / "grad.json"), threshold=threshold)


def _learner(*suggs):
    def fn(records=None, *, now=None):
        return list(suggs)
    return fn


# ── pending list is graduation-aware ──────────────────────────────────

def test_pending_lists_undecided_offers_by_confidence(tmp_path):
    tr = _tracker(tmp_path)
    learner = _learner(_sugg("a", conf=0.4), _sugg("b", conf=0.9))
    pend = ro.pending_offers(learner=learner, tracker=tr)
    assert [o.key for o in pend] == ["b", "a"]     # most confident first
    assert pend[0].accepts == 0 and pend[0].accepts_left == 3


def test_accept_progresses_then_graduates_out_of_pending(tmp_path):
    tr = _tracker(tmp_path, threshold=3)
    learner = _learner(_sugg("arrival:CODING:10:00"))
    key = "arrival:CODING:10:00"

    assert ro.accept(key, tracker=tr) is False     # 1
    assert ro.accept(key, tracker=tr) is False     # 2
    # still pending, progress shown
    o = ro.pending_offers(learner=learner, tracker=tr)[0]
    assert o.accepts == 2 and o.accepts_left == 1

    assert ro.accept(key, tracker=tr) is True      # 3 → graduates
    # now it's gone from the yes/no list …
    assert ro.pending_offers(learner=learner, tracker=tr) == []
    # … and shows up as a runnable, auto-enabled routine
    active = ro.active_routines(learner=learner, tracker=tr)
    assert len(active) == 1
    assert active[0]["enabled"] is True
    assert active[0]["autonomy_level"] == 3
    assert active[0]["source"] == "graduated" and active[0]["key"] == key


# ── revert = hard no ──────────────────────────────────────────────────

def test_revert_suppresses_offer_and_blocks_regraduation(tmp_path):
    tr = _tracker(tmp_path, threshold=2)
    key = "winddown:22:30"
    learner = _learner(_sugg(key))

    ro.accept(key, tracker=tr)
    ro.accept(key, tracker=tr)                      # graduated
    assert ro.active_routines(learner=learner, tracker=tr)

    ro.revert(key, tracker=tr)                      # user undid it
    # not offered again, not active, and re-accepting can't re-graduate
    assert ro.pending_offers(learner=learner, tracker=tr) == []
    assert ro.active_routines(learner=learner, tracker=tr) == []
    assert ro.accept(key, tracker=tr) is False
    assert ro.active_routines(learner=learner, tracker=tr) == []


# ── trust ≠ blank cheque: risky graduated routine stays confirm-gated ─

def test_graduated_but_risky_routine_does_not_auto_enable(tmp_path):
    tr = _tracker(tmp_path, threshold=1)
    key = "auto_pay_rent"
    learner = _learner(_sugg(key, actions=[{"kind": "upi_pay",
                                            "params": {"amt": 15000}}]))
    ro.accept(key, tracker=tr)                      # graduates (threshold 1)
    active = ro.active_routines(learner=learner, tracker=tr)
    assert len(active) == 1
    assert active[0]["enabled"] is False            # NOT auto-fired
    assert active[0]["needs_confirm"] is True
    assert active[0]["autonomy_level"] == 3


def test_reject_is_soft_and_keeps_offer_visible(tmp_path):
    tr = _tracker(tmp_path, threshold=3)
    key = "arrival:WRITING:09:15"
    learner = _learner(_sugg(key))
    ro.reject(key, tracker=tr)
    # a soft dismiss doesn't remove it from the list (may resurface)
    pend = ro.pending_offers(learner=learner, tracker=tr)
    assert [o.key for o in pend] == [key]
    assert pend[0].reverted is False
