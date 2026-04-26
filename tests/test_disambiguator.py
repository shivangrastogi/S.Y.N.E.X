from core.disambiguator import Disambiguator
from core.intent_classifier import Prediction


def _close_pred() -> Prediction:
    """top-1 and top-2 within 0.05; confidence below the high-floor."""
    return Prediction(
        intent="open_app",
        confidence=0.72,
        top3=[("open_app", 0.42), ("close_app", 0.40), ("open_website", 0.18)],
        raw_text="chrome",
        normalized_text="chrome",
    )


def _dominant_pred() -> Prediction:
    return Prediction(
        intent="open_app",
        confidence=0.95,
        top3=[("open_app", 0.92), ("close_app", 0.05), ("open_website", 0.03)],
        raw_text="chrome kholo",
        normalized_text="chrome kholo",
    )


def test_close_call_detected():
    assert Disambiguator().is_close_call(_close_pred())


def test_dominant_not_close_call():
    assert not Disambiguator().is_close_call(_dominant_pred())


def test_no_intent_not_close_call():
    pred = Prediction(intent=None, confidence=0.3, top3=[], raw_text="", normalized_text="")
    assert not Disambiguator().is_close_call(pred)


def test_prompt_mentions_both_options():
    p = _close_pred()
    out = Disambiguator().prompt(p)
    assert "open" in out.lower()
    assert "close" in out.lower()


def test_parse_first_variants():
    d = Disambiguator()
    p = _close_pred()
    for ans in ["1", "first", "pehla", "pehli", "ek", "one"]:
        assert d.parse_answer(ans, p) == "open_app", f"failed for {ans!r}"


def test_parse_second_variants():
    d = Disambiguator()
    p = _close_pred()
    for ans in ["2", "second", "doosra", "dusra", "do", "two"]:
        assert d.parse_answer(ans, p) == "close_app", f"failed for {ans!r}"


def test_parse_intent_id_substring():
    d = Disambiguator()
    p = _close_pred()
    assert d.parse_answer("close_app", p) == "close_app"


def test_parse_unknown_returns_none():
    d = Disambiguator()
    p = _close_pred()
    assert d.parse_answer("idk man", p) is None
    assert d.parse_answer("", p) is None
