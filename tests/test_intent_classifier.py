"""Brain (multilingual encoder + k-NN) tests.

Uses the session-scoped `shared_brain` fixture from conftest so the heavy
model load happens once per pytest run.
"""

import pytest


# Canonical Hinglish samples that should land on the right intent.
# Threshold=0.0 because we want to evaluate the WINNER selection, not
# whether top-1 cosine clears the per-intent confidence floor (that's C7's job).
@pytest.mark.parametrize("text,expected_intent", [
    ("chrome kholo",                    "open_app"),
    ("notepad band karo",               "close_app"),
    ("weather batao",                   "get_weather"),
    ("volume badhao",                   "volume_up"),
    ("volume kam karo",                 "volume_down"),
    ("screenshot lo",                   "take_screenshot"),
    ("calculator open karo",            "open_app"),
    ("youtube pe arijit ka gaana chala do", "play_youtube"),
    ("screen lock karo",                "lock_screen"),
    ("system status batao",             "system_info"),
])
def test_canonical_predictions(shared_brain, text, expected_intent):
    pred = shared_brain.predict(text, threshold=0.0)
    assert pred.intent == expected_intent, (
        f"Expected {expected_intent!r}, got {pred.intent!r}. top3 = {pred.top3}"
    )


def test_top3_present(shared_brain):
    pred = shared_brain.predict("chrome kholo", threshold=0.0)
    assert isinstance(pred.top3, list)
    assert 1 <= len(pred.top3) <= 3
    intent, share = pred.top3[0]
    assert intent == "open_app"
    assert 0.0 <= share <= 1.0


def test_empty_input_returns_no_intent(shared_brain):
    pred = shared_brain.predict("", threshold=0.0)
    assert pred.intent is None
    assert pred.confidence == 0.0


def test_confidence_is_top1_similarity(shared_brain):
    """Confidence should be top-1 cosine similarity, in [0, 1]."""
    pred = shared_brain.predict("chrome kholo", threshold=0.0)
    assert 0.0 <= pred.confidence <= 1.0
    # An exact-match canonical pattern should produce very high confidence.
    assert pred.confidence > 0.85


def test_threshold_gate_returns_none(shared_brain):
    """If threshold > confidence, intent should be None.

    Use an impossible threshold (>1.0) since exact-match patterns produce
    cosine similarity of 1.0 and would otherwise sneak through.
    """
    pred = shared_brain.predict("chrome kholo", threshold=1.5)
    assert pred.intent is None
    # top3 still populated so the disambiguator/UI can show alternatives
    assert len(pred.top3) >= 1
