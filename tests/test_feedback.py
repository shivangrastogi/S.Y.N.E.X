"""FeedbackStore (the contextual-bandit policy) tests."""

import json

import pytest

from core.feedback import (
    DEFAULT_THRESHOLD,
    MAX_THRESHOLD,
    MIN_THRESHOLD,
    FeedbackStore,
)


def _log_executed(fb: FeedbackStore, intent: str, conf: float = 0.8) -> int:
    return fb.log_utterance(
        raw_text="x", normalized_text="x",
        predicted_intent=intent, confidence=conf, top3=[(intent, 1.0)],
        sentiment_label="neutral", sentiment_score=0.0, action_taken="executed",
    )


def test_default_threshold_for_unknown_intent(tmp_feedback_db):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        assert fb.get_threshold("never_seen") == DEFAULT_THRESHOLD
    finally:
        fb.close()


def test_threshold_drifts_down_on_acceptance(tmp_feedback_db):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        for _ in range(10):
            uid = _log_executed(fb, "open_app")
            fb.record_feedback(uid, "accepted")
        threshold = fb.get_threshold("open_app")
        assert threshold < DEFAULT_THRESHOLD, f"expected drift down, got {threshold}"
        assert threshold >= MIN_THRESHOLD
    finally:
        fb.close()


def test_threshold_drifts_up_on_correction(tmp_feedback_db):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        for _ in range(3):
            uid = _log_executed(fb, "play_music", conf=0.6)
            fb.record_feedback(uid, "corrected")
        threshold = fb.get_threshold("play_music")
        assert threshold > DEFAULT_THRESHOLD, f"expected drift up, got {threshold}"
        assert threshold <= MAX_THRESHOLD
    finally:
        fb.close()


def test_correction_rewards_correct_intent(tmp_feedback_db):
    """When user provides correct_intent, that intent gets +1 reward too."""
    fb = FeedbackStore(tmp_feedback_db)
    try:
        for _ in range(5):
            uid = _log_executed(fb, "play_music")
            fb.record_feedback(uid, "corrected", correct_intent="open_app")
        # play_music penalised
        assert fb.get_threshold("play_music") > DEFAULT_THRESHOLD
        # open_app rewarded (positive avg_reward)
        stats = fb.get_intent_stats("open_app")
        assert stats is not None
        assert stats.avg_reward > 0
    finally:
        fb.close()


def test_pending_pattern_queue(tmp_feedback_db):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        uid = fb.log_utterance("z", "z", None, 0.3, [], "neutral", 0.0, "rejected")
        pid = fb.queue_low_confidence(uid, "z", [])
        pending = fb.pending_patterns()
        assert len(pending) == 1
        assert pending[0].id == pid
        assert pending[0].raw_text == "z"
    finally:
        fb.close()


def test_approve_pattern_appends_to_intents_json(tmp_feedback_db, tmp_intents_copy):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        uid = fb.log_utterance("camera kholo", "camera kholo", None,
                               0.3, [], "neutral", 0.0, "rejected")
        pid = fb.queue_low_confidence(uid, "camera kholo", [])

        before = json.load(open(tmp_intents_copy, encoding="utf-8"))
        n_before = len(before["open_app"]["patterns"])

        ok = fb.approve_pattern(pid, "open_app", tmp_intents_copy)
        assert ok is True

        after = json.load(open(tmp_intents_copy, encoding="utf-8"))
        assert len(after["open_app"]["patterns"]) == n_before + 1
        assert "camera kholo" in after["open_app"]["patterns"]
        assert fb.pending_patterns() == []
    finally:
        fb.close()


def test_approve_for_unknown_intent_safe_failure(tmp_feedback_db, tmp_intents_copy):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        uid = fb.log_utterance("foo", "foo", None, 0.3, [], "neutral", 0.0, "rejected")
        pid = fb.queue_low_confidence(uid, "foo", [])
        ok = fb.approve_pattern(pid, "no_such_intent", tmp_intents_copy)
        assert ok is False
    finally:
        fb.close()


def test_unknown_feedback_label_raises(tmp_feedback_db):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        uid = _log_executed(fb, "open_app")
        with pytest.raises(ValueError):
            fb.record_feedback(uid, "wat-no")
    finally:
        fb.close()


def test_threshold_clamped_at_max(tmp_feedback_db):
    fb = FeedbackStore(tmp_feedback_db)
    try:
        # Hammer corrections until threshold tries to go above MAX
        for _ in range(50):
            uid = _log_executed(fb, "play_music")
            fb.record_feedback(uid, "corrected")
        assert fb.get_threshold("play_music") <= MAX_THRESHOLD
    finally:
        fb.close()
