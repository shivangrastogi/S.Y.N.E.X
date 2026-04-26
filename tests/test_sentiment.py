import pytest


@pytest.mark.parametrize("text,label,score_check", [
    ("thank you yaar bahut accha kaam kiya", "positive", lambda s: s > 0.3),
    ("yeh kya bakwaas hai",                  "negative", lambda s: s < -0.2),
    ("chrome kholo",                         "neutral",  lambda s: abs(s) < 0.2),
    ("mast kaam kar rahe ho",                "positive", lambda s: s > 0.2),
    ("bahut kharab response tha",            "negative", lambda s: s < -0.2),
    ("shukriya bhai",                        "positive", lambda s: s > 0.2),
])
def test_sentiment_label_and_score(shared_sentiment, text, label, score_check):
    r = shared_sentiment.classify(text)
    assert r.label == label, f"Wrong label for {text!r}: got {r.label} (score {r.score})"
    assert score_check(r.score), f"Score {r.score} failed check for {text!r}"


def test_sentiment_empty_input(shared_sentiment):
    r = shared_sentiment.classify("")
    assert r.label == "neutral"
    assert r.score == 0.0


def test_sentiment_dataclass_shape(shared_sentiment):
    r = shared_sentiment.classify("anything")
    assert hasattr(r, "label")
    assert hasattr(r, "score")
    assert r.label in {"positive", "neutral", "negative"}
