"""Tests for the Initiative Engine (core.initiative_engine) — salience, ladder
routing, de-dup, anti-nag budget. Injected fakes; no engine/model/disk.
Blueprint Month 4 / Year Q2·M5.
"""

from core.initiative_engine import (
    ACT,
    DROP,
    OFFER,
    Initiative,
    InitiativeEngine,
)


# ── salience ──────────────────────────────────────────────────────

def test_salience_is_product():
    i = Initiative(text="x", kind="k", importance=0.5, timeliness=0.5,
                   confidence=0.5, openness=0.5)
    assert i.score() == 0.0625


# ── fakes ─────────────────────────────────────────────────────────

class _G:
    def __init__(self, gid, text, ask=None):
        self.id, self.text, self.ask = gid, text, ask


class FakeGoals:
    def __init__(self, due):
        self._due = due

    def due(self):
        return self._due


class FakeDecision:
    def __init__(self, outcome, why=""):
        self.outcome, self.why = outcome, why


class FakeGate:
    def __init__(self, outcome="allow", why="ok", quiet=False):
        self._d = FakeDecision(outcome, why)
        self._quiet = quiet

    def authorize(self, action, level, now=None):
        return self._d

    def _in_quiet(self, t):
        return self._quiet


def _eng(due=None, gate_outcome="allow", gate_why="ok", now=1000.0,
         quiet=False, **kw):
    return InitiativeEngine(
        goals_provider=lambda: FakeGoals(due or []),
        gate_provider=lambda: FakeGate(gate_outcome, gate_why, quiet),
        now_fn=lambda: now, **kw)


# ── candidate gathering ───────────────────────────────────────────

def test_due_goal_becomes_candidate():
    e = _eng(due=[_G("g1", "follow up with Rahul")])
    cands = e.candidates()
    assert len(cands) == 1
    assert cands[0].kind == "goal_resume"
    assert "Rahul" in cands[0].text
    assert cands[0].source_id == "goal:g1"


# ── routing ───────────────────────────────────────────────────────

def test_high_salience_acts_when_ladder_allows():
    e = _eng(due=[_G("g1", "x")], gate_outcome="allow")
    out = e.tick()
    assert out and out[0].route == ACT


def test_ladder_deny_downgrades_to_offer():
    # gate says confirm (not allow, not panic/quiet) → offer
    e = _eng(due=[_G("g1", "x")], gate_outcome="confirm", gate_why="rate cap")
    out = e.tick()
    assert out and out[0].route == OFFER


def test_quiet_hours_deny_drops_it():
    e = _eng(due=[_G("g1", "x")], gate_outcome="deny",
             gate_why="Quiet hours — abhi nahi")
    assert e.tick() == []


def test_panic_deny_drops_it():
    e = _eng(due=[_G("g1", "x")], gate_outcome="deny", gate_why="PANIC halt")
    assert e.tick() == []


def test_quiet_hours_silence_all_surfacing():
    # even a high-salience due goal is dropped during quiet hours
    e = _eng(due=[_G("g1", "x")], quiet=True)
    assert e.tick() == []


def test_low_salience_is_dropped():
    low = Initiative(text="meh", kind="k", source_id="s1",
                     importance=0.1, timeliness=0.1, confidence=0.1,
                     openness=0.1)  # score ~0.0001 < offer_threshold
    e = InitiativeEngine(goals_provider=lambda: FakeGoals([]),
                         gate_provider=lambda: FakeGate(),
                         extra_sources=[lambda: [low]], now_fn=lambda: 1000.0)
    assert e.tick() == []


# ── de-dup + anti-nag ─────────────────────────────────────────────

def test_dedup_within_cooldown():
    e = _eng(due=[_G("g1", "x")], cooldown_s=1000.0)
    assert len(e.tick(now=1000.0)) == 1
    # same source again shortly after → suppressed
    assert e.tick(now=1200.0) == []
    # after cooldown → allowed again
    e._now = lambda: 3000.0
    assert len(e.tick(now=3000.0)) == 1


def test_anti_nag_budget_caps_per_hour():
    due = [_G(f"g{i}", f"goal {i}") for i in range(6)]
    e = _eng(due=due, max_per_hour=3, cooldown_s=10.0)
    out = e.tick(now=1000.0)
    assert len(out) == 3       # capped even though 6 were eligible


def test_extra_source_feeds_candidates():
    extra = Initiative(text="mail from boss", kind="mail", source_id="m1",
                       importance=0.9, timeliness=0.9, confidence=0.8,
                       openness=0.8)
    e = InitiativeEngine(goals_provider=lambda: FakeGoals([]),
                         gate_provider=lambda: FakeGate("confirm"),
                         extra_sources=[lambda: [extra]], now_fn=lambda: 1000.0)
    out = e.tick()
    assert out and out[0].kind == "mail"


def test_preview_is_read_only():
    # preview shows the same surfacing but consumes NO budget / cooldown —
    # a dashboard poll must never eat a future real surfacing.
    e = _eng(due=[_G("g1", "x")], cooldown_s=1000.0)
    for _ in range(5):
        assert len(e.preview(now=1000.0)) == 1  # repeatable, no side effects
    out = e.tick(now=1000.0)                    # the real surfacing still fires
    assert len(out) == 1
    assert e.preview(now=1200.0) == []          # now within cooldown → hidden


def test_survives_broken_sources():
    def boom():
        raise RuntimeError("nope")
    e = InitiativeEngine(goals_provider=lambda: (_ for _ in ()).throw(Exception()),
                         gate_provider=lambda: FakeGate(),
                         extra_sources=[boom], now_fn=lambda: 1000.0)
    assert e.tick() == []      # no crash
