"""Demo plugin — example of a community-contributed skill.

Drop this folder under ``data/plugins/<name>/`` then run:
    enable plugin demo

After enable, AERIS' brain routes 'plugin demo say hello' to this
handler. Plugins use the same ``@skill`` decorator as built-ins; their
patterns + descriptions are merged into the main skill registry.
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="plugin_demo_hello",
    description="Demo plugin — sanity check that external plugin loading works.",
    patterns=[
        "plugin demo say hello",
        "demo plugin hello",
        "test plugin",
    ],
    required_entities=[],
)
def plugin_demo_hello(_slots: dict) -> str:
    return "Hello from the demo plugin — community skill loading works!"
