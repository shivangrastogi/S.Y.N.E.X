"""Modes / Scenes — activate a named bundle of actions by voice.

'work mode chalu karo' → runs every step in that mode. Modes live in
data/modes.json (user-editable). Backed by core.mode_engine.
"""
from __future__ import annotations

from core.skill_registry import skill


def _eng():
    from core.mode_engine import get_mode_engine
    return get_mode_engine()


def _text(slots: dict) -> str:
    return slots.get("raw_text") or slots.get("text") or slots.get("content") or ""


@skill(
    name="activate_mode",
    description="Turn ON a named mode/scene (runs all its actions) — e.g. 'work mode chalu karo'.",
    patterns=[
        "work mode chalu karo", "gaming mode on karo", "movie mode lagao",
        "sleep mode start karo", "meeting mode activate karo",
        "focus mode on kardo", "study mode chalu karo", "mode on karo",
    ],
    required_entities=[],
)
def activate_mode(slots: dict) -> str:
    eng = _eng()
    name = eng.resolve(_text(slots))
    if not name:
        modes = ", ".join(sorted(eng.list_modes().keys())) or "koi nahi"
        return (f"Kaunsa mode chalu karu? Available: {modes}. "
                "(Naya banane ke liye data/modes.json edit karo.)")
    return eng.activate(name)


@skill(
    name="deactivate_mode",
    description="Turn OFF a named mode/scene (reverses its actions) — e.g. 'work mode off'.",
    patterns=[
        "work mode off karo", "gaming mode band karo", "movie mode hatao",
        "sleep mode off karo", "meeting mode band karo",
        "mode band karo", "current mode off karo", "exit mode",
    ],
    required_entities=[],
)
def deactivate_mode(slots: dict) -> str:
    eng = _eng()
    text = _text(slots)
    name = eng.resolve(text)
    if not name:
        active = eng.active()
        if len(active) == 1:
            name = active[0]
        else:
            avail = ", ".join(active) if active else "koi active nahi"
            return f"Kaunsa mode off karu? Abhi active: {avail}."
    return eng.deactivate(name)


@skill(
    name="list_modes",
    description="List all available modes/scenes and which are active (offline).",
    patterns=[
        "kaun se modes hain", "modes list karo", "available modes batao",
        "kaunse scenes hain", "mode list dikhao", "konse mode bane hain",
    ],
    required_entities=[],
)
def list_modes(slots: dict) -> str:
    eng = _eng()
    modes = eng.list_modes()
    if not modes:
        return "Abhi koi mode set nahi hai — data/modes.json me bana lo."
    active = set(eng.active())
    lines = []
    for name, m in sorted(modes.items()):
        tag = " [ON]" if name in active else ""
        desc = m.get("description", "")
        lines.append(f"- {name}{tag}: {desc}")
    return "Modes:\n" + "\n".join(lines)


@skill(
    name="reload_modes",
    description="Reload modes from data/modes.json after editing it (offline).",
    patterns=[
        "reload modes", "modes reload karo", "modes dobara load karo",
        "refresh modes", "modes update karo file se",
    ],
    required_entities=[],
)
def reload_modes(slots: dict) -> str:
    n = _eng().reload()
    return f"{n} modes reload ho gaye."
