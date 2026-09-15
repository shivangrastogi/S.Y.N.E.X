"""Graduated routines → live automations: the learning loop's last mile. Real
AutomationEngine on a tmp file (no cron thread — we never call start()), a
scripted learner + tmp graduation tracker. See core/graduated_routines.py.
"""
from core.automation import AutomationEngine
from core.routine_learner import Suggestion
from core.routine_graduation import GraduationTracker
from core import routine_offers as ro
from core import graduated_routines as gr


def _sugg(key, *, actions=None, cron="0 10 * * 1-5"):
    return Suggestion(
        key=key, title=f"offer {key}", detail="pattern", confidence=0.9,
        evidence_days=5,
        routine_spec={"name": key.replace(":", "_"), "enabled": False,
                      "description": "learned",
                      "trigger": {"kind": "time", "params": {"cron": cron}},
                      "actions": actions or [{"kind": "notify",
                                              "params": {"title": "AERIS",
                                                         "body": "ready"}}]},
    )


def _learner(*suggs):
    def fn(records=None, *, now=None):
        return list(suggs)
    return fn


def _engine(tmp_path):
    return AutomationEngine(routines_path=str(tmp_path / "routines.json"))


def _tracker(tmp_path, threshold=2):
    return GraduationTracker(str(tmp_path / "grad.json"), threshold=threshold)


def _offers_fn(learner, tracker):
    def fn(records=None, learner=None, tracker=None, now=None):
        return ro.active_routines(learner=_offers_fn.learner,
                                  tracker=_offers_fn.tracker)
    _offers_fn.learner, _offers_fn.tracker = learner, tracker
    return fn


# ── a graduated routine becomes a live, enabled automation ────────────

def test_graduated_routine_materializes_and_fires_ready(tmp_path):
    eng = _engine(tmp_path)
    tr = _tracker(tmp_path, threshold=2)
    key = "arrival:CODING:10:00"
    learner = _learner(_sugg(key))

    # not yet graduated → nothing materializes
    res = gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert res["created"] == [] and eng.list_routines() == []

    ro.accept(key, tracker=tr)
    ro.accept(key, tracker=tr)                 # graduates (threshold 2)

    res = gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert res["created"] == [key]
    rns = eng.list_routines()
    assert len(rns) == 1
    r = rns[0]
    assert r.enabled is True
    assert r.trigger.kind == "time"
    assert r.actions[0].kind == "notify"
    assert f"[grad:{key}]" in r.description


# ── idempotent: re-sync doesn't duplicate ─────────────────────────────

def test_resync_is_idempotent(tmp_path):
    eng = _engine(tmp_path)
    tr = _tracker(tmp_path, threshold=1)
    key = "winddown:22:30"
    learner = _learner(_sugg(key))
    ro.accept(key, tracker=tr)                 # graduates

    r1 = gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    r2 = gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert r1["created"] == [key]
    assert r2["created"] == [] and r2["kept"] == [key]
    assert len(eng.list_routines()) == 1       # not duplicated


# ── revert retires the live automation ────────────────────────────────

def test_revert_retires_the_live_automation(tmp_path):
    eng = _engine(tmp_path)
    tr = _tracker(tmp_path, threshold=1)
    key = "arrival:WRITING:09:00"
    learner = _learner(_sugg(key))
    ro.accept(key, tracker=tr)
    gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert len(eng.list_routines()) == 1

    ro.revert(key, tracker=tr)                 # user undid it
    res = gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert res["retired"] == [key]
    assert eng.list_routines() == []           # gone from the executor


# ── risky graduated routine is NOT materialized (stays confirm-gated) ─

def test_risky_graduated_routine_is_not_materialized(tmp_path):
    eng = _engine(tmp_path)
    tr = _tracker(tmp_path, threshold=1)
    key = "auto_pay_rent"
    learner = _learner(_sugg(key, actions=[{"kind": "run_skill",
                                            "params": {"name": "upi_pay"}}]))
    # run_skill isn't in the safe-auto set → active_routines leaves it disabled
    ro.accept(key, tracker=tr)
    res = gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert res["created"] == []
    assert eng.list_routines() == []           # never entered the executor


# ── the user's own hand-made routines are never touched ───────────────

def test_user_routines_are_untouched(tmp_path):
    eng = _engine(tmp_path)
    tr = _tracker(tmp_path, threshold=1)
    mine = eng.create_routine(name="my morning", trigger=Trigger_time(),
                              actions=[__notify()], enabled=True)
    key = "winddown:22:30"
    learner = _learner(_sugg(key))
    ro.accept(key, tracker=tr)
    gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    # my routine survives graduation churn
    ro.revert(key, tracker=tr)
    gr.sync(eng, offers_fn=_offers_fn(learner, tr))
    assert eng.get_routine(mine.id) is not None
    assert eng.get_routine(mine.id).enabled is True


# tiny builders for the last test
from core.automation import Trigger, Action


def Trigger_time():
    return Trigger(kind="time", params={"cron": "0 8 * * *"})


def __notify():
    return Action(kind="notify", params={"title": "me", "body": "hi"})
