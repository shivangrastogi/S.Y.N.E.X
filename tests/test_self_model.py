"""Tests for the Self-Model (core.self_model) — read-only introspection with
injected fakes; no engine/model/disk. Blueprint Month 1.
"""

from core.self_model import SelfModel, SelfState


class _Goal:
    def __init__(self, text, state):
        self.text, self.state = text, state


class FakeGoals:
    def __init__(self, goals):
        self._g = goals

    def open_goals(self):
        return [g for g in self._g if g.state not in ("done", "dropped")]


class FakeLedger:
    def __init__(self, entries):
        self._e = entries

    def recent(self, n=12):
        return self._e[-n:]


def _sm(skills=None, goals=None, ledger=None, panic=False, mem=0):
    return SelfModel(
        skills_provider=lambda: {n: None for n in (skills or [])},
        goals_provider=lambda: FakeGoals(goals or []),
        ledger_provider=lambda: FakeLedger(ledger or []),
        telemetry_provider=lambda: mem,
        panic_provider=lambda: panic,
    )


# ── snapshot ──────────────────────────────────────────────────────

def test_snapshot_counts_skills_and_capabilities():
    sm = _sm(skills=["torch_on", "send_whatsapp", "call_contact", "get_weather"])
    st = sm.snapshot()
    assert st.skills_count == 4
    assert st.capabilities.get("device") == 1
    assert st.capabilities.get("message") == 1
    assert st.capabilities.get("call") == 1


def test_snapshot_active_goals():
    sm = _sm(goals=[_Goal("plan trip", "acting"), _Goal("old", "done")])
    st = sm.snapshot()
    assert len(st.active_goals) == 1
    assert st.active_goals[0]["text"] == "plan trip"


def test_confidence_drops_with_errors():
    good = [{"decision": "allow", "action": "x", "why": "w"} for _ in range(8)]
    bad = [{"decision": "deny", "action": "y", "why": "no"} for _ in range(2)]
    sm = _sm(ledger=good + bad)
    st = sm.snapshot()
    assert st.confidence == 0.8       # 2 errors / 10
    assert st.recent_errors           # errors surfaced


def test_panic_sets_not_awake():
    st = _sm(panic=True).snapshot()
    assert st.awake is False
    assert "panic" in st.autonomy


# ── describe() ────────────────────────────────────────────────────

def test_describe_capabilities():
    sm = _sm(skills=["torch_on", "send_whatsapp"])
    out = sm.describe("tu kya kar sakta hai")
    assert "kaam kar sakta" in out


def test_describe_doing_with_acting_goal():
    sm = _sm(goals=[_Goal("Goa trip research", "acting")])
    out = sm.describe("abhi kya kar raha hai")
    assert "Goa trip research" in out


def test_describe_how_are_you():
    sm = _sm(skills=["get_weather"])
    out = sm.describe("kaisa hai")
    assert "confidence" in out.lower() or "%" in out


def test_describe_why_reads_last_action():
    led = [{"decision": "allow", "action": "silence_phone",
            "why": "meeting mein the"}]
    out = _sm(ledger=led).describe("ye kyun kiya")
    assert "silence_phone" in out and "meeting" in out


def test_describe_default_summary():
    out = _sm(skills=["a", "b"]).describe("")
    assert "skills" in out and "goals" in out


def test_readonly_never_crashes_on_missing_providers():
    # all providers raise → snapshot still returns a valid state
    sm = SelfModel(
        skills_provider=lambda: (_ for _ in ()).throw(RuntimeError()),
        goals_provider=lambda: (_ for _ in ()).throw(RuntimeError()),
        ledger_provider=lambda: (_ for _ in ()).throw(RuntimeError()),
        telemetry_provider=lambda: (_ for _ in ()).throw(RuntimeError()),
        panic_provider=lambda: False,
    )
    st = sm.snapshot()
    assert isinstance(st, SelfState)
    assert st.skills_count == 0
