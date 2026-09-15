"""End-to-end coverage for the app-launching pipeline upgrades:

* Exact-pattern fast path in JarvisBrain.predict
* Expanded open_app / close_app intent patterns
* Regex fallback in EntityExtractor for apps not in the gazetteer
* Brain LRU prediction cache (repeated query → same Prediction object)

These tests exercise the brain + entity-extractor live (no mocks). They
piggyback on the session-scoped fixtures in conftest so the encoder is only
loaded once for the whole suite.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ── Exact-pattern fast path ─────────────────────────────────────────

def test_exact_match_open_notepad_routes_to_open_app(shared_brain):
    p = shared_brain.predict("open notepad")
    assert p.intent == "open_app", (
        f"'open notepad' must route to open_app; got {p.intent!r}. "
        f"The exact-match fast path should bypass the neural model."
    )
    assert p.confidence == 1.0


def test_exact_match_is_case_insensitive(shared_brain):
    a = shared_brain.predict("open notepad")
    b = shared_brain.predict("OPEN NOTEPAD")
    c = shared_brain.predict("Open  Notepad ")
    for p in (a, b, c):
        assert p.intent == "open_app"
        assert p.confidence == 1.0


def test_exact_match_separates_note_from_notepad(shared_brain):
    """The cue word 'note' must not bleed into notepad-shaped queries."""
    note_pred = shared_brain.predict("note bana do")
    notepad_pred = shared_brain.predict("notepad kholo")
    assert note_pred.intent == "create_note"
    assert notepad_pred.intent == "open_app"


def test_unknown_phrase_falls_through_to_classifier(shared_brain):
    """A phrase nobody added as a pattern should NOT get a confidence=1.0
    fast-path hit — it should fall through to the real classifier."""
    p = shared_brain.predict("wibblefibble bramblestone glorp")
    # Either it routes to some intent at sub-1.0 confidence, or returns
    # None/low-conf — the only thing that's WRONG is confidence == 1.0
    # (which would mean the fast path mis-fired).
    assert p.confidence < 1.0


# ── Expanded open_app pattern coverage ──────────────────────────────


def _open_app_patterns_present(*phrases: str) -> bool:
    import json
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "intents.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    patt = {p.lower().strip() for p in data["open_app"]["patterns"]}
    return all(p.lower() in patt for p in phrases)


def test_open_app_covers_common_windows_apps():
    """Every 'open X' for a built-in Windows app should be a verbatim pattern
    so the fast path catches it (the neural model was misrouting these)."""
    # "open settings" and "open file explorer" are intentionally absent:
    # dedicated skills own them since the 2026-07-04 pattern unification
    # (open_settings_panel / open_explorer_here — both verbatim patterns,
    # so the fast path still catches them).
    must_have = [
        "open notepad", "open calculator", "open paint",
        "open task manager", "open mail",
        "open photos", "open camera",
        "open cmd", "open powershell", "open store",
    ]
    missing = [p for p in must_have if not _open_app_patterns_present(p)]
    assert not missing, f"open_app pattern set missing: {missing}"


# ── Entity-extractor regex fallback ─────────────────────────────────

def test_extractor_resolves_unknown_app_via_regex(shared_extractor):
    """When the gazetteer doesn't list an app (krita, obsidian), the
    'open <X>' regex fallback should still pass X through so the executor
    gets a chance to launch it via `start`."""
    cases = [
        ("open krita",         "krita"),
        ("launch obsidian",    "obsidian"),
        ("blender chalu karo", "blender"),
        ("postman kholo",      "postman"),
    ]
    for text, expected in cases:
        ents = shared_extractor.extract(text, "open_app")
        assert ents.get("app_name") == expected, (
            f"{text!r} → {ents}; expected app_name={expected!r}"
        )


def test_extractor_prefers_gazetteer_when_available(shared_extractor):
    """A known alias must not be overwritten by the regex fallback."""
    ents = shared_extractor.extract("open google chrome", "open_app")
    # Either "chrome" (canonical) or "google chrome" depending on greediness.
    assert ents.get("app_name") in ("chrome", "google chrome")


# ── Brain prediction LRU cache ──────────────────────────────────────

def test_predict_cache_returns_same_object_on_repeat(shared_brain):
    """Two identical predict() calls in a row should hit the LRU and
    return the very same Prediction instance."""
    a = shared_brain.predict("open chrome")
    b = shared_brain.predict("open chrome")
    assert a is b, "predict cache should return identical instance on repeat"


def test_predict_cache_can_be_cleared(shared_brain):
    a = shared_brain.predict("open notepad")
    shared_brain.clear_prediction_cache()
    b = shared_brain.predict("open notepad")
    # After clear, equal but not same instance.
    assert a is not b
    assert a.intent == b.intent == "open_app"
