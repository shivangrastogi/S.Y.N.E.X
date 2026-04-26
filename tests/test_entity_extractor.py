"""Entity extractor tests — uses shared_extractor (no model load needed)."""

import pytest


@pytest.mark.parametrize("text,intent,slot,expected", [
    # Residual span — query / content
    ("youtube pe arijit ka latest gaana chala do", "play_youtube", "query",  "arijit ka latest gaana"),
    ("python tutorial google pe search karo",     "search_web",   "query",  "python tutorial"),
    # Gazetteer — app_name (longest-alias-wins)
    ("chrome kholo",                              "open_app",     "app_name", "chrome"),
    ("google chrome open karo",                   "open_app",     "app_name", "chrome"),
    # URL regex (with auto-scheme)
    ("github.com kholo",                          "open_website", "url", "https://github.com"),
    ("https://github.com/foo kholo",              "open_website", "url", "https://github.com/foo"),
    # Math expression
    ("12 + 7 * 3 calculate karo",                 "calculate",    "expression", "12 + 7 * 3"),
    # Person via "with X" shortcut
    ("with shivang at 5 pm meeting lagao",        "schedule_meeting", "person", "shivang"),
    ("with shivang at 5 pm meeting lagao",        "schedule_meeting", "time",   "5 pm"),
    # Time inside a reminder
    ("5 baje shaam ko milk lena yaad dilana",     "set_reminder", "time",    "5 baje shaam"),
    ("5 baje shaam ko milk lena yaad dilana",     "set_reminder", "message", "milk lena"),
])
def test_extract(shared_extractor, text, intent, slot, expected):
    out = shared_extractor.extract(text, intent)
    assert out.get(slot) == expected, f"Got {out!r}"


def test_intent_with_no_required_entities(shared_extractor):
    """get_weather has no required_entities — should return empty dict."""
    assert shared_extractor.extract("weather batao", "get_weather") == {}


def test_unknown_intent_returns_empty(shared_extractor):
    """An intent not present in intents.json yields {} (no crash)."""
    assert shared_extractor.extract("anything", "no_such_intent") == {}


def test_empty_text(shared_extractor):
    assert shared_extractor.extract("", "open_app") == {}
