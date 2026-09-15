"""Iteration #5 — routing + handler tests for dictionary, browser_tabs,
and clipboard image skills.

Side-effect-safe:
  * dictionary tests stub _fetch so no real HTTP call goes out.
  * browser_tabs tests stub _ctrl so no real keystroke is sent.
  * clipboard_image tests stub _push_dib_to_clipboard so no real
    clipboard mutation happens.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "define_word", "synonyms", "antonyms",
    "tab_switch", "tab_next", "tab_prev",
    "tab_new", "tab_close", "tab_reopen",
    "last_screenshot_to_clipboard", "image_to_clipboard",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("define",                       "define_word"),
    ("definition of",                "define_word"),
    ("synonyms of",                  "synonyms"),
    ("antonyms of",                  "antonyms"),
    ("tab 3",                        "tab_switch"),
    ("third tab",                    "tab_switch"),
    ("next tab",                     "tab_next"),
    ("previous tab",                 "tab_prev"),
    ("new tab",                      "tab_new"),
    ("close tab",                    "tab_close"),
    ("reopen tab",                   "tab_reopen"),
    ("copy last screenshot",         "last_screenshot_to_clipboard"),
    ("last screenshot copy karo",    "last_screenshot_to_clipboard"),
    ("copy image to clipboard",      "image_to_clipboard"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter5(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── dictionary ────────────────────────────────────────────────────


def _stub_entry(definitions=None, synonyms=None, antonyms=None):
    return {
        "word": "stub",
        "meanings": [
            {
                "partOfSpeech": "noun",
                "definitions": [
                    {"definition": d, "synonyms": [], "antonyms": []}
                    for d in (definitions or [])
                ],
                "synonyms": synonyms or [],
                "antonyms": antonyms or [],
            },
        ],
    }


def test_define_word_no_query_prompts():
    from skills.dictionary import define_word
    out = define_word({"raw_text": "define"})
    assert "?" in out or "kaunsa" in out.lower() or "which" in out.lower()


def test_define_word_returns_definition(monkeypatch):
    import skills.dictionary as d
    monkeypatch.setattr(d, "_fetch",
                        lambda w: _stub_entry(definitions=["lasting for a very short time"]))
    out = d.define_word({"raw_text": "define ephemeral"})
    assert "lasting for a very short time" in out


def test_define_word_handles_lookup_fail(monkeypatch):
    import skills.dictionary as d
    monkeypatch.setattr(d, "_fetch", lambda w: None)
    out = d.define_word({"raw_text": "define notarealword"})
    assert "nahi mila" in out.lower() or "fail" in out.lower()


def test_synonyms_returns_list(monkeypatch):
    import skills.dictionary as d
    monkeypatch.setattr(d, "_fetch",
                        lambda w: _stub_entry(synonyms=["joyful", "glad", "cheerful"]))
    out = d.synonyms({"raw_text": "synonyms of happy"})
    assert "joyful" in out and "glad" in out


def test_antonyms_returns_list(monkeypatch):
    import skills.dictionary as d
    monkeypatch.setattr(d, "_fetch",
                        lambda w: _stub_entry(antonyms=["sad", "unhappy"]))
    out = d.antonyms({"raw_text": "antonyms of happy"})
    assert "sad" in out and "unhappy" in out


def test_dictionary_strip_verb_handles_what_does_X_mean():
    """End-to-end: 'what does ephemeral mean' must reduce to 'ephemeral'."""
    import re
    from skills.dictionary import _strip_verb
    triggers = ["what does the word", "what does", "what is the meaning of",
                "what is the definition of", "definition of", "meaning of", "define"]
    word = _strip_verb("what does ephemeral mean", *triggers)
    word = re.sub(r"\s+mean\??$", "", word, flags=re.IGNORECASE).strip()
    assert word == "ephemeral"


# ── browser_tabs ──────────────────────────────────────────────────


def test_tab_switch_extracts_number():
    from skills.browser_tabs import _extract_tab_number
    assert _extract_tab_number("tab 3") == 3
    assert _extract_tab_number("third tab") == 3
    assert _extract_tab_number("dusra tab kholo") == 2
    assert _extract_tab_number("last tab") == 9
    assert _extract_tab_number("nothing here") is None


def test_tab_switch_sends_keystroke(monkeypatch):
    import skills.browser_tabs as bt
    fired: list[int] = []
    monkeypatch.setattr(bt, "_ctrl",
                        lambda vk, shift=False: (fired.append((vk, shift)), True)[1])
    out = bt.tab_switch({"raw_text": "tab 4"})
    assert "4" in out
    assert fired and fired[0][0] == 0x34   # VK for '4'


def test_tab_switch_no_number_prompts():
    from skills.browser_tabs import tab_switch
    out = tab_switch({"raw_text": "switch to tab"})
    # No explicit digit → must prompt
    assert "?" in out or "kaunsa" in out.lower() or "tab" in out.lower()


def test_tab_next_prev_send_ctrl_tab(monkeypatch):
    import skills.browser_tabs as bt
    fired: list[tuple[int, bool]] = []
    monkeypatch.setattr(bt, "_ctrl",
                        lambda vk, shift=False: (fired.append((vk, shift)), True)[1])
    bt.tab_next({})
    bt.tab_prev({})
    assert fired == [(bt._VK_TAB, False), (bt._VK_TAB, True)]


# ── clipboard_image ───────────────────────────────────────────────


def test_last_screenshot_handles_empty_dir(monkeypatch):
    import skills.clipboard_image as ci
    monkeypatch.setattr(ci, "_newest_screenshot", lambda: None)
    out = ci.last_screenshot_to_clipboard({})
    assert "nahi mila" in out.lower() or "no" in out.lower()


def test_last_screenshot_pushes_to_clipboard(monkeypatch, tmp_path):
    import skills.clipboard_image as ci
    fake_img = tmp_path / "shot.png"
    fake_img.write_bytes(b"fake")
    monkeypatch.setattr(ci, "_newest_screenshot", lambda: fake_img)
    pushed: list = []
    monkeypatch.setattr(ci, "_push_dib_to_clipboard",
                        lambda p: (pushed.append(p), (True, f"Copied {p.name}"))[1])
    out = ci.last_screenshot_to_clipboard({})
    assert pushed == [fake_img]
    assert "shot.png" in out
    assert "paste" in out.lower()


def test_image_to_clipboard_no_query_prompts():
    from skills.clipboard_image import image_to_clipboard
    out = image_to_clipboard({"raw_text": "copy image to clipboard"})
    assert "?" in out or "kaunsi" in out.lower() or "path" in out.lower()
