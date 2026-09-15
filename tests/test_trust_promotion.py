"""Earned-trust recommendations (§6.32) — pure ledger analysis, no disk.

The rule this file exists to protect: **nothing here ever raises a grant.**
A system that quietly grants itself more power is what an autonomy ladder is
for preventing.
"""

from __future__ import annotations

import pytest

from core.autonomy import HARD_CAP, L0_ASK, L1_SUGGEST, L2_DRAFT, L3_ACT
from core.trust_promotion import (
    Promotion, assess, initiative_candidates, looks_failed, reset_nudge_clock,
    tally,
)

NOW = 1_000_000.0
DAY = 86400.0


class _Gate:
    def __init__(self, **grants):
        self.grants = grants
        self.set_calls = []

    def granted_level(self, cls):
        return self.grants.get(cls, L1_SUGGEST)

    def set_grant(self, cls, level):      # must never be called from here
        self.set_calls.append((cls, level))
        return level


def _rows(cls="app", n=10, decision="allow", result="ok", age_days=1.0):
    return [{"ts": NOW - age_days * DAY, "cls": cls, "decision": decision,
             "result": result} for _ in range(n)]


class TestTally:
    def test_counts_by_class_and_decision(self):
        rows = _rows("app", 3) + _rows("media", 2, decision="deny")
        t = tally(rows, now=NOW)
        assert t["app"].allowed == 3 and t["media"].denied == 2

    def test_rows_outside_the_window_are_ignored(self):
        t = tally(_rows("app", 5, age_days=90), now=NOW)
        assert t == {}

    def test_failures_are_detected_from_the_result_text(self):
        t = tally(_rows("app", 2, result="Error: could not open"), now=NOW)
        assert t["app"].failed == 2 and t["app"].clean is False

    def test_malformed_rows_do_not_lose_the_others(self):
        rows = [{"nope": 1}, {"ts": "bad"}, None] + _rows("app", 3)
        t = tally([r for r in rows if r is not None], now=NOW)
        assert t["app"].allowed == 3

    def test_rows_without_a_class_are_skipped(self):
        assert tally([{"ts": NOW, "decision": "allow"}], now=NOW) == {}

    def test_failure_markers(self):
        assert looks_failed("Error: nope") and looks_failed("timeout")
        assert not looks_failed("SUCCESS_EXECUTE|opened chrome")
        assert not looks_failed(None)


class TestAssess:
    def test_a_clean_well_exercised_class_earns_a_step(self):
        g = _Gate(app=L1_SUGGEST)
        got = assess(_rows("app", 12), g, now=NOW)
        assert len(got) == 1
        p = got[0]
        assert p.cls == "app" and p.current == L1_SUGGEST
        assert p.proposed == L1_SUGGEST + 1 and p.samples == 12

    def test_too_few_runs_is_not_evidence(self):
        g = _Gate(app=L1_SUGGEST)
        assert assess(_rows("app", 3), g, now=NOW) == []

    def test_a_single_denial_resets_the_case(self):
        g = _Gate(app=L1_SUGGEST)
        rows = _rows("app", 12) + _rows("app", 1, decision="deny")
        assert assess(rows, g, now=NOW) == []

    def test_a_single_failure_resets_the_case(self):
        g = _Gate(app=L1_SUGGEST)
        rows = _rows("app", 12) + _rows("app", 1, result="Error: boom")
        assert assess(rows, g, now=NOW) == []

    def test_the_strongest_evidence_comes_first(self):
        g = _Gate(app=L1_SUGGEST, media=L1_SUGGEST)
        got = assess(_rows("app", 9) + _rows("media", 30), g, now=NOW)
        assert [p.cls for p in got] == ["media", "app"]

    def test_a_recommendation_reads_as_a_question(self):
        g = _Gate(app=L1_SUGGEST)
        s = assess(_rows("app", 12), g, now=NOW)[0].sentence()
        assert "app" in s and "L1" in s and "L2" in s and s.endswith("?")


class TestTheCapsAreAbsolute:
    """No amount of good behaviour unlocks an irreversible action."""

    @pytest.mark.parametrize("cls", sorted(HARD_CAP))
    def test_a_capped_class_is_never_proposed_past_its_ceiling(self, cls):
        g = _Gate(**{cls: HARD_CAP[cls]})
        assert assess(_rows(cls, 50), g, now=NOW) == []

    def test_a_capped_class_below_its_ceiling_can_still_step_up(self):
        g = _Gate(payment=L0_ASK)
        got = assess(_rows("payment", 20), g, now=NOW)
        assert got and got[0].proposed <= HARD_CAP["payment"]

    def test_a_class_already_at_the_top_is_not_proposed(self):
        g = _Gate(read=5)
        assert assess(_rows("read", 50), g, now=NOW) == []


class TestItNeverPromotesItself:
    def test_assess_does_not_touch_the_gate(self):
        g = _Gate(app=L1_SUGGEST)
        assess(_rows("app", 30), g, now=NOW)
        assert g.set_calls == []

    def test_the_initiative_is_a_notify_not_an_act(self, monkeypatch):
        """Raising autonomy is the one decision that must never be taken
        autonomously — so the offer asks, at notify level."""
        reset_nudge_clock()

        class _Ledger:
            def all(self):
                return _rows("app", 12)

        class _G(_Gate):
            def __init__(self):
                super().__init__(app=L1_SUGGEST)
                self.ledger = _Ledger()

        gate = _G()
        import core.autonomy as autonomy
        monkeypatch.setattr(autonomy, "get_gate", lambda: gate)
        out = initiative_candidates(now_fn=lambda: NOW)
        assert len(out) == 1
        ini = out[0]
        assert ini.kind == "trust_promotion"
        assert ini.action == "notify_user" and ini.requested_level == 2
        assert gate.set_calls == []

    def test_the_nudge_is_rate_limited(self, monkeypatch):
        reset_nudge_clock()

        class _Ledger:
            def all(self):
                return _rows("app", 12)

        class _G(_Gate):
            def __init__(self):
                super().__init__(app=L1_SUGGEST)
                self.ledger = _Ledger()

        import core.autonomy as autonomy
        monkeypatch.setattr(autonomy, "get_gate", lambda: _G())
        assert initiative_candidates(now_fn=lambda: NOW)
        assert initiative_candidates(now_fn=lambda: NOW + 60) == []
        assert initiative_candidates(now_fn=lambda: NOW + 10 * DAY)

    def test_nothing_to_recommend_is_silence(self, monkeypatch):
        reset_nudge_clock()

        class _G(_Gate):
            def __init__(self):
                super().__init__(app=L1_SUGGEST)
                self.ledger = type("L", (), {"all": lambda s: []})()

        import core.autonomy as autonomy
        monkeypatch.setattr(autonomy, "get_gate", lambda: _G())
        assert initiative_candidates(now_fn=lambda: NOW) == []

    def test_a_broken_gate_is_silence_not_a_crash(self, monkeypatch):
        reset_nudge_clock()
        import core.autonomy as autonomy

        def _boom():
            raise RuntimeError("no ledger")

        monkeypatch.setattr(autonomy, "get_gate", _boom)
        assert initiative_candidates(now_fn=lambda: NOW) == []


class TestWiring:
    def test_the_engine_registers_the_trust_source(self):
        import inspect
        from core import initiative_engine
        src = inspect.getsource(initiative_engine.get_engine)
        assert "_trust_src" in src and "trust_promotion" in src


class TestRefusalsCountAgainstIt:
    """§6.33. Before declines were recorded, a class the user had refused ten
    times looked identical to one they were never asked about — and the first
    cut of this module would have proposed raising it."""

    def test_a_single_refusal_resets_the_case(self):
        g = _Gate(message=L1_SUGGEST)
        rows = _rows("message", 20) + _rows("message", 1, decision="declined")
        assert assess(rows, g, now=NOW) == []

    def test_refusals_are_tallied_as_asked_and_declined(self):
        t = tally(_rows("message", 3, decision="declined"), now=NOW)
        assert t["message"].asked == 3 and t["message"].declined == 3

    def test_a_confirmation_alone_is_an_ask_not_a_refusal(self):
        t = tally(_rows("message", 4, decision="confirm"), now=NOW)
        assert t["message"].asked == 4 and t["message"].declined == 0
        assert t["message"].clean is True

    def test_consent_rate_is_none_when_never_asked(self):
        t = tally(_rows("app", 5), now=NOW)
        assert t["app"].consent_rate is None

    def test_consent_rate_reflects_refusals(self):
        rows = _rows("message", 3, decision="confirm") + \
            _rows("message", 1, decision="declined")
        t = tally(rows, now=NOW)
        assert t["message"].asked == 4 and t["message"].declined == 1
        assert t["message"].consent_rate == pytest.approx(0.75)

    def test_approved_confirmations_strengthen_the_stated_reason(self):
        g = _Gate(app=L1_SUGGEST)
        rows = _rows("app", 12) + _rows("app", 3, decision="confirm")
        got = assess(rows, g, now=NOW)
        assert got and "confirmations all approved" in got[0].reason

    def test_declines_do_not_inflate_budgets(self):
        """`Ledger._today()` counts only `allow` rows, which is why a new
        decision value was used instead of reusing `deny` — a refusal must not
        eat into the day's rate cap."""
        import core.autonomy as autonomy
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            led = autonomy.Ledger(os.path.join(d, "l.jsonl"), now_fn=lambda: NOW)
            led.record(action="send_message", args={}, cls="message",
                       level=2, decision="declined", why="no", result="DECLINED")
            assert led.count_today("message") == 0
            led.record(action="send_message", args={}, cls="message",
                       level=2, decision="allow", why="ok", result="sent")
            assert led.count_today("message") == 1


class TestDeclinedActionExtraction:
    """`goal_system.declined_action` — the engine needs the action a parked
    goal was asking about, and the scratchpad nests it."""

    def _goal(self, scratch):
        from core.goal_system import Goal
        g = Goal(text="do the thing")
        g.scratchpad = scratch
        return g

    def test_prefers_the_blocked_step(self):
        from core.goal_system import declined_action
        g = self._goal([
            {"action": {"kind": "tool", "name": "search_web", "args": {}},
             "observation": "ok", "blocked": False},
            {"action": {"kind": "tool", "name": "send_message",
                        "args": {"to": "rahul"}},
             "observation": "AWAITING", "blocked": True},
        ])
        assert declined_action(g) == ("send_message", {"to": "rahul"})

    def test_falls_back_to_the_last_named_step(self):
        from core.goal_system import declined_action
        g = self._goal([{"action": {"kind": "tool", "name": "open_app",
                                    "args": {}}, "blocked": False}])
        assert declined_action(g)[0] == "open_app"

    def test_an_empty_or_malformed_trace_yields_nothing(self):
        from core.goal_system import declined_action
        assert declined_action(self._goal([])) == ("", {})
        assert declined_action(self._goal([{"nope": 1}, "junk"])) == ("", {})
