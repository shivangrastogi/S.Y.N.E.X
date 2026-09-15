"""Continual-learning loop: harvest, dedupe, registry, eval gate (fast lane).

No encoder / neural model loads here — the LearningStore is exercised with
an explicit ``known_intents`` dict so skill discovery never runs.
"""

from __future__ import annotations

import json
import os

import pytest

from core.feedback import FeedbackStore
from core.learning_loop import LearningStore
from core import model_registry
from core.intent_eval import EvalResult, ItemResult, gate, load_golden


KNOWN = {
    "open_app": {"patterns": ["open chrome", "chrome kholo"]},
    "close_app": {"patterns": ["chrome band karo"]},
    "play_music": {"patterns": ["gana bajao"]},
}


def _store(tmp_path, db):
    return LearningStore(path=str(tmp_path / "learned.json"), db_path=db)


def _log(fb, text, intent, conf, feedback=None, correct=None):
    uid = fb.log_utterance(
        raw_text=text, normalized_text=text.lower(),
        predicted_intent=intent, confidence=conf,
        top3=[(intent or "open_app", conf)], sentiment_label="neutral",
        sentiment_score=0.0, action_taken="executed",
    )
    if feedback:
        fb.record_feedback(uid, feedback, correct_intent=correct)
    return uid


# ── harvest ──────────────────────────────────────────────────────────── #

class TestHarvest:
    def test_accepted_utterance_becomes_trainable_sample(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "chrome chala de na", "open_app", 0.81, "accepted")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        r = store.harvest(known_intents=KNOWN)
        assert r.added == 1
        assert store.as_intent_dict() == {"open_app": ["chrome chala de na"]}

    def test_correction_is_gold_even_at_low_confidence(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "band karde ye sab", "play_music", 0.31,
             "corrected", correct="close_app")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        store.harvest(known_intents=KNOWN)
        assert store.as_intent_dict() == {"close_app": ["band karde ye sab"]}
        assert store.samples[0].source == "corrected"

    def test_exact_match_rows_are_skipped(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "open chrome", "open_app", 1.0, "accepted")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        r = store.harvest(known_intents=KNOWN)
        assert r.added == 0 and r.skipped_exact == 1

    def test_known_corpus_pattern_is_skipped(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "chrome kholo", "open_app", 0.9, "accepted")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        r = store.harvest(known_intents=KNOWN)
        assert r.added == 0 and r.skipped_known == 1

    def test_low_confidence_accept_goes_to_review_not_auto(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "kuch bhi chala de", "play_music", 0.52, "accepted")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        store.harvest(known_intents=KNOWN)
        assert store.as_intent_dict() == {}          # review ≠ trainable
        assert store.samples[0].status == "review"

    def test_unknown_intent_and_unfeedbacked_rows_ignored(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "warp speed lagao", "warp_drive", 0.9, "accepted")   # unknown intent
        _log(fb, "hmm kya bolu", "open_app", 0.7)                     # no feedback
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        r = store.harvest(known_intents=KNOWN)
        assert r.added == 0 and r.skipped_invalid == 1 and r.scanned == 1

    def test_reharvest_is_idempotent_and_repeat_bumps_times_seen(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "chrome chala de na", "open_app", 0.8, "accepted")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        assert store.harvest(known_intents=KNOWN).added == 1
        assert store.harvest(known_intents=KNOWN).scanned == 0  # watermark moved
        # Same phrase accepted again later → bump, not duplicate.
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "chrome chala de na", "open_app", 0.85, "accepted")
        fb.close()
        store2 = _store(tmp_path, tmp_feedback_db)
        r = store2.harvest(known_intents=KNOWN)
        assert r.bumped == 1 and r.added == 0
        assert store2.samples[0].times_seen == 2

    def test_correction_upgrades_review_sample_to_gold(self, tmp_path, tmp_feedback_db):
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "kuch bhi chala de", "play_music", 0.52, "accepted")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        store.harvest(known_intents=KNOWN)
        assert store.samples[0].status == "review"
        fb = FeedbackStore(tmp_feedback_db)
        _log(fb, "kuch bhi chala de", "open_app", 0.4,
             "corrected", correct="play_music")
        fb.close()
        store = _store(tmp_path, tmp_feedback_db)
        store.harvest(known_intents=KNOWN)
        assert store.samples[0].status == "auto"
        assert store.as_intent_dict() == {"play_music": ["kuch bhi chala de"]}


# ── status / curation ────────────────────────────────────────────────── #

class TestStoreCuration:
    def test_status_counts_and_mark_trained(self, tmp_path, tmp_feedback_db):
        store = _store(tmp_path, tmp_feedback_db)
        for i in range(3):
            store.add_manual(f"phrase number {i}", "open_app")
        s = store.status()
        assert s["trainable_samples"] == 3 and s["new_since_last_train"] == 3
        store.mark_trained()
        assert store.status()["new_since_last_train"] == 0

    def test_set_status_rejected_removes_from_training(self, tmp_path, tmp_feedback_db):
        store = _store(tmp_path, tmp_feedback_db)
        store.add_manual("galat phrase hai ye", "open_app")
        assert store.set_status("galat phrase hai ye", "rejected")
        assert store.as_intent_dict() == {}

    def test_persistence_roundtrip(self, tmp_path, tmp_feedback_db):
        store = _store(tmp_path, tmp_feedback_db)
        store.add_manual("naya wala phrase", "close_app")
        again = _store(tmp_path, tmp_feedback_db)
        assert again.as_intent_dict() == {"close_app": ["naya wala phrase"]}


# ── intent_loader merge ──────────────────────────────────────────────── #

class TestLoaderMerge:
    def test_learned_patterns_merge_into_corpus(self, tmp_path, monkeypatch):
        from core import intent_loader
        learned = {"version": 1, "meta": {}, "samples": [
            {"text": "chrome chala de na", "intent": "open_app", "status": "auto"},
            {"text": "rejected wala", "intent": "open_app", "status": "rejected"},
            {"text": "naya intent phrase", "intent": "brand_new_intent",
             "status": "auto"},
        ]}
        lp = tmp_path / "learned.json"
        lp.write_text(json.dumps(learned), encoding="utf-8")
        intents_path = tmp_path / "intents.json"
        intents_path.write_text(json.dumps(
            {"open_app": {"patterns": ["open chrome"]}}), encoding="utf-8")
        monkeypatch.setattr(intent_loader, "LEARNED_PATTERNS_PATH", str(lp))
        merged = intent_loader.load_all_intents(str(intents_path))
        assert "chrome chala de na" in merged["open_app"]["patterns"]
        assert "rejected wala" not in merged["open_app"]["patterns"]
        assert merged["brand_new_intent"]["patterns"] == ["naya intent phrase"]

    def test_learned_dedupes_against_existing_patterns(self, tmp_path, monkeypatch):
        from core import intent_loader
        lp = tmp_path / "learned.json"
        lp.write_text(json.dumps({"version": 1, "meta": {}, "samples": [
            {"text": "open chrome", "intent": "open_app", "status": "auto"},
        ]}), encoding="utf-8")
        intents_path = tmp_path / "intents.json"
        intents_path.write_text(json.dumps(
            {"open_app": {"patterns": ["open chrome"]}}), encoding="utf-8")
        monkeypatch.setattr(intent_loader, "LEARNED_PATTERNS_PATH", str(lp))
        merged = intent_loader.load_all_intents(str(intents_path))
        assert merged["open_app"]["patterns"].count("open chrome") == 1


# ── model registry ───────────────────────────────────────────────────── #

def _fake_model_dir(path, generation, val_acc=0.9):
    os.makedirs(os.path.join(path, "model"))
    os.makedirs(os.path.join(path, "tokenizer"))
    with open(os.path.join(path, "model", "weights.bin"), "w") as f:
        f.write("fake")
    with open(os.path.join(path, "labels.json"), "w") as f:
        json.dump({"id2label": {"0": "open_app"}}, f)
    with open(os.path.join(path, "metadata.json"), "w") as f:
        json.dump({"generation": generation, "best_val_acc": val_acc,
                   "mode": "fresh"}, f)


class TestModelRegistry:
    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        self.live = str(tmp_path / "intent_neural")
        self.staging = str(tmp_path / "intent_neural_staging")
        self.archive = str(tmp_path / "archive")
        monkeypatch.setattr(model_registry, "LIVE_DIR", self.live)
        monkeypatch.setattr(model_registry, "HISTORY_PATH",
                            str(tmp_path / "history.json"))

    def test_first_promote_no_live_model(self):
        _fake_model_dir(self.staging, generation=1)
        model_registry.promote_staging(self.staging, self.live, self.archive)
        assert os.path.isdir(self.live) and not os.path.isdir(self.staging)
        assert model_registry.history()[-1]["generation"] == 1

    def test_promote_archives_previous_and_rollback_restores(self):
        _fake_model_dir(self.live, generation=1, val_acc=0.7)
        _fake_model_dir(self.staging, generation=2, val_acc=0.9)
        model_registry.promote_staging(self.staging, self.live, self.archive)
        with open(os.path.join(self.live, "metadata.json")) as f:
            assert json.load(f)["generation"] == 2
        assert model_registry.rollback(self.live, self.archive)
        with open(os.path.join(self.live, "metadata.json")) as f:
            assert json.load(f)["generation"] == 1

    def test_missing_staging_raises(self):
        with pytest.raises(model_registry.PromotionError):
            model_registry.promote_staging(self.staging, self.live, self.archive)

    def test_archive_pruned_to_keep_limit(self):
        for gen in range(1, 5):
            if os.path.isdir(self.staging):
                raise AssertionError("staging should be consumed each round")
            _fake_model_dir(self.staging, generation=gen)
            model_registry.promote_staging(self.staging, self.live, self.archive)
        archived = os.listdir(self.archive)
        assert len(archived) == model_registry.KEEP_ARCHIVES


# ── eval gate ────────────────────────────────────────────────────────── #

def _result(model, rows, known=None):
    r = EvalResult(model=model, known_labels=set(known or []))
    for text, gold, pred in rows:
        r.items.append(ItemResult(text=text, gold=gold, also_ok=[],
                                  predicted=pred, confidence=0.9))
    return r


class TestEvalGate:
    def test_also_ok_counts_as_correct(self):
        item = ItemResult(text="t", gold="current_time", also_ok=["get_time"],
                          predicted="get_time", confidence=0.8)
        assert item.correct

    def test_no_live_model_passes(self):
        new = _result("staging", [("a", "open_app", "open_app")])
        ok, _ = gate(None, new)
        assert ok

    def test_improvement_passes_and_regression_fails(self):
        old = _result("live", [("a", "open_app", "open_app"),
                               ("b", "close_app", "open_app")],
                      known=["open_app", "close_app"])
        better = _result("staging", [("a", "open_app", "open_app"),
                                     ("b", "close_app", "close_app")])
        worse = _result("staging", [("a", "open_app", "close_app"),
                                    ("b", "close_app", "open_app")])
        assert gate(old, better)[0]
        assert not gate(old, worse)[0]

    def test_new_intents_not_held_against_old_model(self):
        # Old model knew only open_app and scored 100% on it. New model keeps
        # that and adds a brand-new intent it happens to miss — the miss on
        # the new intent must not fail the gate.
        old = _result("live", [("a", "open_app", "open_app")],
                      known=["open_app"])
        new = _result("staging", [("a", "open_app", "open_app"),
                                  ("z", "brand_new", "open_app")])
        ok, why = gate(old, new)
        assert ok, why

    def test_load_golden_filters_unknown_intents(self, tmp_path):
        p = tmp_path / "golden.json"
        p.write_text(json.dumps({"items": [
            {"text": "chrome chala", "intent": "open_app"},
            {"text": "warp jump", "intent": "warp_drive"},
        ]}), encoding="utf-8")
        items = load_golden(str(p), known_intents={"open_app"})
        assert [i["intent"] for i in items] == ["open_app"]
