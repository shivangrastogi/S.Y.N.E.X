"""Theme switcher voice surface.

Skills:
  * ``theme_dark``  / ``theme_light``  / ``theme_cyber``
  * ``theme_cycle`` — rotate to next theme
  * ``theme_status``— current theme + available
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="theme_dark",
    description="Switch the AERIS UI to the dark theme.",
    patterns=[
        "dark theme", "theme dark", "set theme dark",
        "go dark", "dark mode on", "dark mode",
        "kala theme", "dark theme karo",
    ],
    required_entities=[],
)
def theme_dark(_slots: dict) -> str:
    from core.theme import apply_theme
    _, msg = apply_theme("dark")
    return msg


@skill(
    name="theme_light",
    description="Switch the AERIS UI to the light theme.",
    patterns=[
        "light theme", "theme light", "set theme light",
        "go light", "light mode on", "light mode",
        "white theme", "light theme karo",
    ],
    required_entities=[],
)
def theme_light(_slots: dict) -> str:
    from core.theme import apply_theme
    _, msg = apply_theme("light")
    return msg


@skill(
    name="theme_cyber",
    description="Switch the AERIS UI to the cyber (neon-on-black) theme.",
    patterns=[
        "cyber theme", "theme cyber", "set theme cyber",
        "go cyber", "hacker theme", "matrix theme",
        "neon theme",
    ],
    required_entities=[],
)
def theme_cyber(_slots: dict) -> str:
    from core.theme import apply_theme
    _, msg = apply_theme("cyber")
    return msg


@skill(
    name="theme_cycle",
    description="Rotate to the next available theme.",
    patterns=[
        "cycle theme", "next theme", "theme switch",
        "rotate theme", "theme cycle", "agla theme",
    ],
    required_entities=[],
)
def theme_cycle(_slots: dict) -> str:
    from core.theme import cycle_theme
    _, msg = cycle_theme()
    return msg


@skill(
    name="theme_status",
    description="Report the current theme + available options.",
    patterns=[
        "theme status", "current theme", "what theme is on",
        "kaunsa theme chal raha hai", "theme kya hai",
        "list themes",
    ],
    required_entities=[],
)
def theme_status(_slots: dict) -> str:
    from core.theme import current_theme, list_themes
    return f"Theme: {current_theme()} · Available: {', '.join(list_themes())}."
