"""Cross-core integration for the Sentient Partner — the six faculties working
together on one scenario, at the module level (no engine boot). Proves the cores
actually interoperate, not just pass in isolation.
"""
from __future__ import annotations

import core.anticipation as ANT
from core.affect import AffectiveCore
from core.anticipation import Anticipator
from core.cognition import CognitionLoop
from core.context_bus import ContextBus
from core.interpreter import Interpreter
from core.trust_ladder import AUTO, classify


def test_learned_habit_flows_through_the_cores(tmp_path, monkeypatch):
    # 1. PERCEIVE — the Context Bus records the morning routine.
    bus = ContextBus()
    bus.record_command("time kya hua", "get_time")

    # 2. ANTICIPATE — learn that, in the morning after get_time, the user opens Gmail.
    ant = Anticipator(path=str(tmp_path / "a.json"), enabled=True, min_support=3)
    for _ in range(5):
        ant.observe("get_time", "gmail kholo", "open_app", "morning")
    monkeypatch.setattr(ANT, "_DEFAULT", ant)          # cognition pulls this singleton

    # 3. ACT-SAFELY — opening an app is AUTO-tier (local + reversible).
    assert classify("open_app").level == AUTO

    # 4. THINK — cognition forms the learned habit as its own proactive thought.
    cog = CognitionLoop(enabled=True, cooldown_s=1200.0)
    snap = bus.snapshot(now=1000.0, mood="content", hour=9)     # 9am → morning
    thought = cog.reflect(snap, now=1000.0)
    assert thought is not None and thought.kind == "habit"
    assert "gmail kholo" in thought.message and thought.trust == AUTO

    # 5. UNDERSTAND — a fuzzy reasoning query routes to the observe/act agent.
    assert Interpreter().plan("konsi file sabse purani hai").strategy == "agent"

    # 6. FEEL — sustained negativity moves mood off neutral (drives care/suppression).
    aff = AffectiveCore(persist_path=str(tmp_path / "aff.json"))
    for _ in range(4):
        aff.observe(-0.85, failure=True)
    assert aff.mood() in ("frustrated", "low", "tired")


def test_bad_mood_makes_cognition_hold_back(tmp_path, monkeypatch):
    """The emotional core and the reasoner are wired: a frustrated user is not
    pestered with soft proactive ideas — only genuinely urgent nudges survive."""
    ant = Anticipator(path=str(tmp_path / "a.json"), enabled=True, min_support=3)
    for _ in range(5):
        ant.observe("get_time", "gmail kholo", "open_app", "morning")
    monkeypatch.setattr(ANT, "_DEFAULT", ant)

    bus = ContextBus()
    bus.record_command("time kya hua", "get_time")
    cog = CognitionLoop(enabled=True, cooldown_s=1200.0)

    # content → the habit surfaces
    ok = cog.reflect(bus.snapshot(now=1000.0, mood="content", hour=9), now=1000.0)
    assert ok is not None and ok.kind == "habit"

    # frustrated → the same habit is held back (fresh loop, no cooldown carryover)
    cog2 = CognitionLoop(enabled=True, cooldown_s=1200.0)
    held = cog2.reflect(bus.snapshot(now=2000.0, mood="frustrated", hour=9), now=2000.0)
    assert held is None
