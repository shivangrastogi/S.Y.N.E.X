"""Routine builder — engine create/delete + dialog build logic.

Engine tests use a temp routines path (never the user's routines.json).
Dialog tests run Qt offscreen and exercise ``_build()`` directly — the
validation lives there, no clicking required.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.automation import Action, AutomationEngine, Trigger


@pytest.fixture
def engine(tmp_path):
    return AutomationEngine(routines_path=str(tmp_path / "routines.json"))


# ── engine.create_routine / delete_routine ───────────────────────────

def test_create_daily_routine_persists_and_registers(engine, tmp_path):
    r = engine.create_routine(
        name="Evening wrap-up",
        trigger=Trigger(kind="time", params={"cron": "30 21 * * *"}),
        actions=[Action(kind="run_skill",
                        params={"name": "system_stats", "slots": {}})],
    )
    assert r.id == "evening_wrap_up"
    assert r.enabled
    # Live matcher registered — fires without restart/reload.
    assert r.id in engine._matchers
    # Persisted atomically.
    data = json.loads((tmp_path / "routines.json").read_text(encoding="utf-8"))
    assert data["routines"][0]["name"] == "Evening wrap-up"
    assert data["routines"][0]["trigger"]["params"]["cron"] == "30 21 * * *"


def test_create_dedupes_id(engine):
    a = engine.create_routine(name="Focus", trigger=Trigger(kind="manual"),
                              actions=[Action(kind="notify", params={"body": "x"})])
    b = engine.create_routine(name="Focus", trigger=Trigger(kind="manual"),
                              actions=[Action(kind="notify", params={"body": "y"})])
    assert a.id == "focus" and b.id == "focus_2"


def test_interval_routine_gets_first_deadline(engine):
    r = engine.create_routine(
        name="Stretch reminder",
        trigger=Trigger(kind="interval", params={"seconds": 1800}),
        actions=[Action(kind="notify", params={"body": "stretch!"})],
    )
    assert r.id in engine._next_fire


def test_delete_routine(engine, tmp_path):
    r = engine.create_routine(name="Temp", trigger=Trigger(kind="manual"),
                              actions=[Action(kind="notify", params={"body": "x"})])
    assert engine.delete_routine(r.id) is True
    assert engine.delete_routine(r.id) is False
    data = json.loads((tmp_path / "routines.json").read_text(encoding="utf-8"))
    assert data["routines"] == []


def test_manual_created_routine_runs(engine):
    r = engine.create_routine(
        name="Ping me",
        trigger=Trigger(kind="manual"),
        actions=[Action(kind="delay", params={"seconds": 0})],
    )
    assert engine.run_routine(r.id, reason="test") is True


# ── dialog build/validation (offscreen Qt) ───────────────────────────

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _dialog(qapp):
    from ui.jarvis_v31.tab_panels import _RoutineBuilderDialog
    return _RoutineBuilderDialog()


def test_dialog_builds_daily_trigger(qapp):
    d = _dialog(qapp)
    d._trig_kind.setCurrentIndex(0)
    d._trig_value.setText("21:30")
    d._action_rows[0][0].setCurrentText("Run skill")
    d._action_rows[0][1].setText("system_stats")
    trig, actions = d._build()
    assert trig.kind == "time" and trig.params["cron"] == "30 21 * * *"
    assert actions[0].kind == "run_skill"
    assert actions[0].params["name"] == "system_stats"


def test_dialog_url_gets_scheme(qapp):
    d = _dialog(qapp)
    d._trig_kind.setCurrentIndex(3)          # manual
    d._action_rows[0][0].setCurrentText("Open URL")
    d._action_rows[0][1].setText("github.com")
    _, actions = d._build()
    assert actions[0].params["value"] == "https://github.com"


def test_dialog_rejects_bad_time(qapp):
    d = _dialog(qapp)
    d._trig_kind.setCurrentIndex(0)
    d._trig_value.setText("25:99")
    d._action_rows[0][0].setCurrentText("Notify")
    d._action_rows[0][1].setText("hello")
    with pytest.raises(ValueError):
        d._build()


def test_dialog_rejects_no_actions(qapp):
    d = _dialog(qapp)
    d._trig_kind.setCurrentIndex(3)
    with pytest.raises(ValueError):
        d._build()
