"""brain_health + retrain pipeline + learning skill (fast lane — no models)."""

from __future__ import annotations

import json
import os

import pytest

from core import brain_health as bh
from core.feedback import FeedbackStore
from core.brain_health import HealthReport, collect, format_report, speak_summary


class _StubLearningStore:
    """Deterministic stand-in for LearningStore inside collect()/skills."""
    def __init__(self, *a, **k):
        pass

    def status(self):
        return {
            "total_samples": 20, "trainable_samples": 18, "review_samples": 2,
            "new_since_last_train": 18, "retrain_recommended": True,
            "last_harvest_at": "2026-07-19T10:00:00", "last_trained_at": None,
            "by_intent": {"open_app": 9, "close_app": 5, "play_music": 4},
        }


@pytest.fixture
def stub_learning(monkeypatch):
    import core.learning_loop as ll
    monkeypatch.setattr(ll, "LearningStore", _StubLearningStore)


@pytest.fixture
def quiet_cards(tmp_path, monkeypatch):
    """Point the report-card fallback at an empty dir for determinism."""
    monkeypatch.setattr(bh, "CARD_DIR", str(tmp_path / "cards"))


def _seed_db(db_path):
    fb = FeedbackStore(db_path)
    for _ in range(8):
        uid = fb.log_utterance("chrome kholo", "chrome kholo", "open_app",
                               0.9, [("open_app", 0.9)], "neutral", 0.0,
                               "executed")
        fb.record_feedback(uid, "accepted")
    for _ in range(2):
        uid = fb.log_utterance("gana band", "gana band", "play_music",
                               0.5, [("play_music", 0.5)], "neutral", 0.0,
                               "executed")
        fb.record_feedback(uid, "corrected", correct_intent="stop_music")
    # low-confidence hotspot rows (no feedback)
    for _ in range(3):
        fb.log_utterance("hmm", "hmm", "doc_query", 0.4,
                         [("doc_query", 0.4)], "neutral", 0.0, "chat_fallback")
    fb.close()


class TestCollect:
    def test_usage_rates_confusions_and_hotspots(self, tmp_path, tmp_feedback_db,
                                                 stub_learning, quiet_cards):
        _seed_db(tmp_feedback_db)
        r = collect(window_days=7, db_path=tmp_feedback_db,
                    live_dir=str(tmp_path / "nomodel"), check_hash=False)
        assert r.accepted == 8 and r.corrected == 2
        assert r.acceptance_rate == 0.8 and r.correction_rate == 0.2
        assert r.chat_fallbacks == 3
        assert {"from": "play_music", "to": "stop_music", "n": 2} in r.confusion_pairs
        assert any(h["intent"] == "doc_query" for h in r.low_conf_hotspots)
        assert r.learned_trainable == 18 and r.new_since_train == 18

    def test_live_metadata_read(self, tmp_path, tmp_feedback_db,
                                stub_learning, quiet_cards):
        live = tmp_path / "live"
        live.mkdir()
        (live / "metadata.json").write_text(json.dumps({
            "generation": 3, "best_val_acc": 0.9, "golden_acc": 0.85,
            "trained_at": "2026-07-19T00:00:00"}), encoding="utf-8")
        r = collect(window_days=7, db_path=tmp_feedback_db,
                    live_dir=str(live), check_hash=False)
        assert r.generation == 3 and r.golden_acc == 0.85

    def test_empty_world_does_not_crash(self, tmp_path, stub_learning,
                                        quiet_cards):
        r = collect(window_days=7, db_path=str(tmp_path / "absent.sqlite"),
                    live_dir=str(tmp_path / "nomodel"), check_hash=False)
        assert r.acceptance_rate is None
        assert isinstance(format_report(r), str)
        assert isinstance(speak_summary(r), str)


class TestScoreAndAdvise:
    def test_score_renormalises_over_available_parts(self):
        r = HealthReport(window_days=7)
        r.golden_acc = 0.8          # weight 0.25
        r.neural_active = True      # weight 0.15
        bh._score(r)
        # (0.25*0.8 + 0.15*1.0) / 0.40 = 0.875
        assert r.health_score == 88

    def test_no_data_leaves_score_none(self):
        r = HealthReport(window_days=7)
        bh._score(r)
        assert r.health_score is None

    def test_advise_triggers(self):
        r = HealthReport(window_days=7)
        r.neural_active = False
        r.new_since_train = bh.RETRAIN_AT_NEW_SAMPLES
        r.corrected = bh.CORRECTION_SPIKE_MIN
        bh._advise(r)
        assert r.retrain_recommended and len(r.reasons) == 3

    def test_healthy_brain_no_retrain(self):
        r = HealthReport(window_days=7)
        r.neural_active = True
        r.new_since_train = 2
        bh._advise(r)
        assert not r.retrain_recommended


class TestRetrainPipeline:
    def test_preflight_shape(self):
        from core.retrain import preflight
        pf = preflight()
        assert set(pf) == {"aeris_running", "deps_ok", "mode"}
        assert pf["mode"] in ("incremental", "fresh")

    def test_dry_run_changes_nothing_and_prints_plan(self, capsys,
                                                     stub_learning):
        from core.retrain import main
        assert main(["--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "[plan]" in out and "dry run" in out
        assert "harvest" in out and "train" in out

    def test_dry_run_colab_plan(self, capsys, stub_learning):
        from core.retrain import main
        assert main(["--dry-run", "--colab", "--skip-harvest"]) == 0
        out = capsys.readouterr().out
        assert "Colab" in out and "harvest" not in out.split("[plan]")[1]


class TestLearningSkill:
    def test_learning_status_reports_and_advises(self, stub_learning):
        from skills.learning_skill import learning_status
        msg = learning_status({})
        assert "18" in msg and "open app" in msg
        assert "core.retrain" in msg          # retrain due -> command surfaced

    def test_learning_status_empty_store(self, monkeypatch):
        import core.learning_loop as ll

        class _Empty(_StubLearningStore):
            def status(self):
                s = _StubLearningStore.status(self)
                s.update(total_samples=0, trainable_samples=0,
                         review_samples=0, new_since_last_train=0,
                         retrain_recommended=False, by_intent={})
                return s
        monkeypatch.setattr(ll, "LearningStore", _Empty)
        from skills.learning_skill import learning_status
        assert "kuch naya nahi seekha" in learning_status({})

    def test_brain_health_skill_speaks_summary(self, monkeypatch):
        r = HealthReport(window_days=30)
        r.health_score = 91
        r.neural_active = True
        r.generation = 2
        r.golden_acc = 0.9
        r.confusion_pairs = [{"from": "play_music", "to": "stop_music", "n": 2}]
        monkeypatch.setattr(bh, "collect", lambda **k: r)
        from skills.learning_skill import brain_health
        msg = brain_health({})
        assert "91" in msg and "Generation 2" in msg
        assert "play music" in msg and "stop music" in msg

    def test_patterns_are_collision_free(self):
        # Regression net on top of test_pattern_collisions: the two new
        # skills must own their phrases exclusively.
        from core.skill_registry import discover_skills, REGISTRY
        discover_skills("skills")
        mine = {p.strip().lower()
                for name in ("learning_status", "brain_health")
                for p in REGISTRY[name].patterns}
        others = {p.strip().lower()
                  for name, sk in REGISTRY.items()
                  if name not in ("learning_status", "brain_health")
                  for p in (sk.patterns or [])}
        assert not (mine & others)
