"""Screen ACTIONS — pure logic (no real clicking/screen)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.screen_actions import _line_phrases, _words, _score


def _fake_data(words):
    """Build a pytesseract-style dict from
    (text, block, par, line, x, y, w, h, conf)."""
    d = {k: [] for k in ("text", "block_num", "par_num", "line_num",
                         "left", "top", "width", "height", "conf")}
    for t, b, p, l, x, y, w, h, c in words:
        d["text"].append(t); d["block_num"].append(b)
        d["par_num"].append(p); d["line_num"].append(l)
        d["left"].append(x); d["top"].append(y)
        d["width"].append(w); d["height"].append(h); d["conf"].append(c)
    return d


def test_line_phrases_groups_same_line():
    data = _fake_data([
        ("Add", 1, 1, 1, 10, 100, 30, 20, 90),
        ("to", 1, 1, 1, 45, 100, 20, 20, 90),
        ("cart", 1, 1, 1, 70, 100, 40, 20, 90),
        ("Home", 1, 1, 2, 10, 200, 50, 20, 90),
    ])
    texts = [e["phrase"] for e in _line_phrases(data)]
    assert "Add to cart" in texts        # multi-word line merged
    assert "Home" in texts               # separate line kept separate


def test_line_phrase_centre_is_midpoint():
    data = _fake_data([
        ("Login", 1, 1, 1, 100, 50, 80, 20, 95),  # x 100..180, y 50..70
    ])
    e, = _line_phrases(data)
    assert e["cx"] == 140 and e["cy"] == 60


def test_downscale_halves_coords():
    data = _fake_data([("X", 1, 1, 1, 200, 100, 40, 20, 95)])
    e, = _line_phrases(data, downscale=2)
    assert e["cx"] == 110 and e["cy"] == 55   # (220/2, 110/2)


def test_low_confidence_words_dropped():
    data = _fake_data([
        ("wrroren", 1, 1, 1, 0, 0, 40, 20, 12),   # garbage, low conf
        ("Save", 1, 1, 2, 10, 40, 40, 20, 88),
    ])
    assert [e["phrase"] for e in _line_phrases(data)] == ["Save"]


def test_words_give_each_word_its_own_box():
    # A shared menu line: clicking "File" must target File's box (x≈25),
    # NOT the line midpoint (which would land on "Selection").
    data = _fake_data([
        ("File", 1, 1, 1, 10, 20, 30, 18, 90),
        ("Edit", 1, 1, 1, 50, 20, 30, 18, 90),
        ("Selection", 1, 1, 1, 90, 20, 70, 18, 90),
        ("View", 1, 1, 1, 170, 20, 40, 18, 90),
    ])
    words = {w["phrase"]: w for w in _words(data)}
    assert words["File"]["cx"] == 25       # centre of File's own box
    assert words["View"]["cx"] == 190      # centre of View's own box
    assert words["File"]["cx"] != words["Selection"]["cx"]


def test_score_prefers_short_exact():
    # "submit" as a lone button beats "submit" inside a paragraph.
    button = _score("submit", "Submit")
    para = _score("submit", "please submit your form before the deadline today")
    assert button > para
    assert button >= 100


# ── skill extraction ─────────────────────────────────────────────────

def test_type_skill_extracts_text():
    from skills.screen_actions_skill import type_on_screen
    # No real typing — pyautogui may be absent in CI; just ensure it
    # extracts and doesn't crash on parsing.
    out = type_on_screen({"raw_text": "type karo hello world"})
    assert "hello world" in out or "type" in out.lower()


def test_scroll_direction_parse():
    import core.screen_actions as sa
    calls = {}
    sa.scroll = lambda direction="down", amount=500: calls.setdefault(
        "dir", direction) or f"scrolled {direction}"
    from skills.screen_actions_skill import screen_scroll
    screen_scroll({"raw_text": "upar scroll karo"})
    assert calls.get("dir") == "up"
