"""Locks in help_catalog's category drill-down (2026-08-02): "system commands" →
the System category, while a generic "what can you do" stays None (→ overview).
Pure function — pass the category titles directly, no registry/engine needed.
"""
from __future__ import annotations

import pytest

from skills.help_catalog import _detect_category

_TITLES = [
    "🖥️ System, Power & Diagnostics",
    "🪟 Apps & Window Management",
    "🌐 Web & Browser",
    "🎵 Media & Music",
    "📋 Clipboard Superpowers",
    "📄 Documents, Files & Q&A",
    "💻 Developer Tools",
    "✍️ Text, Writing & Language (AI)",
    "🧮 Math, Finance & Calculators",
    "⏰ Time, Productivity & Automation",
    "🎙️ Voice & Speech",
    "👁️ Vision, Gestures & Screen",
    "🧠 Memory & Knowledge Graph",
    "🎉 Fun & Casual",
]


@pytest.mark.parametrize("query,expect_substr", [
    ("system commands kya hain", "System"),
    ("math commands", "Math"),
    ("calculator commands", "Math"),
    ("clipboard skills", "Clipboard"),
    ("voice commands", "Voice"),
    ("memory commands", "Memory"),
    ("music commands", "Media"),
    ("web commands", "Web"),
    ("developer commands", "Developer"),
    ("text commands", "Text"),
    ("reminder commands", "Productivity"),
    ("fun commands", "Fun"),
])
def test_detect_category_hits(query, expect_substr):
    got = _detect_category(query, _TITLES)
    assert got is not None and expect_substr in got, f"{query!r} → {got!r}"


@pytest.mark.parametrize("query", [
    "what can you do", "kya kya kar sakte ho", "help",
    "mere jarvis mein kya hai", "features batao",
])
def test_detect_category_generic_is_none(query):
    # Generic capability questions must NOT drill into a category.
    assert _detect_category(query, _TITLES) is None
