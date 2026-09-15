"""Screen-Aware Agent — fast logic tests (no OCR/LLM).

The capture→OCR→LLM path is integration-tested live (it needs a real
screen + model). These pin the pure pieces: question extraction and
graceful degradation when sight/thought aren't available.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skills.screen_agent_skill import _extract_question


def test_strips_leading_trigger():
    assert _extract_question("screen dekh ke batao ye error kya hai") \
        == "ye error kya hai"
    assert _extract_question("look at my screen and summarise this") \
        == "summarise this"


def test_strips_trailing_trigger():
    assert _extract_question("ye kya hai on screen") == "ye kya hai"


def test_keeps_plain_question():
    assert _extract_question("is email ka reply likho") \
        == "is email ka reply likho"


def test_empty_after_strip_falls_back_to_raw():
    # Only a trigger, nothing else — keep the original so assist() still
    # runs with a default question.
    out = _extract_question("screen dekh ke")
    assert out  # non-empty


def test_assist_without_ocr_degrades_gracefully(monkeypatch):
    import core.screen_agent as sa
    monkeypatch.setattr(sa, "_grab_screen_text", lambda: "")
    msg = sa.assist("kuch bhi")
    assert "padh nahi" in msg.lower() or "ocr" in msg.lower()


def test_assist_without_llm_returns_screen_text(monkeypatch):
    import core.screen_agent as sa
    monkeypatch.setattr(sa, "_grab_screen_text",
                        lambda: "Error: connection refused on port 8080")
    monkeypatch.setattr(sa, "_active_app", lambda: "Chrome — localhost")

    class _NoLLM:
        def available(self):
            return False

    import core.local_llm as ll
    monkeypatch.setattr(ll, "get", lambda: _NoLLM())
    out = sa.assist("ye error kya hai")
    assert "connection refused" in out  # raw screen text surfaced
