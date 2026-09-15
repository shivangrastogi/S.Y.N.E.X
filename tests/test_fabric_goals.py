"""Goals as a federated memory source (§6.26).

The fabric already unified episodic + KG + user memory; standing intentions
were the one store the planner couldn't see. Fast lane: real `Goal` objects,
fake stores, no encoder, no disk.
"""

from __future__ import annotations

import time

from core.goal_system import Goal
from core.memory_fabric import MemoryFabric


class _Goals:
    """The slice of GoalStore the fabric uses."""

    def __init__(self, *goals):
        self.goals = list(goals)

    def open_goals(self):
        return [g for g in self.goals if g.is_open]


def _fabric(*goals, now=1_000_000.0):
    return MemoryFabric(
        semantic_provider=lambda: None,
        kg_provider=lambda: None,
        user_memory_provider=lambda: None,
        goal_provider=lambda: _Goals(*goals),
        now_fn=lambda: now,
    )


def _goal(text, **kw):
    kw.setdefault("created", 1_000_000.0)
    kw.setdefault("updated", 1_000_000.0)
    return Goal(text=text, **kw)


class TestRecall:
    def test_a_relevant_open_goal_is_recalled(self):
        f = _fabric(_goal("book the delhi flight"))
        hits = f.recall("delhi flight")
        assert hits and hits[0].kind == "goal"
        assert "book the delhi flight" in hits[0].text

    def test_an_unrelated_goal_stays_out(self):
        """Surfacing every open goal on each turn is a different question, and
        would push unrelated intentions into every plan."""
        f = _fabric(_goal("book the delhi flight"))
        assert f.recall("what is the weather") == []

    def test_kind_filtering_works_both_ways(self):
        f = _fabric(_goal("book the delhi flight"))
        assert f.recall("delhi flight", kinds=["goal"])
        assert f.recall("delhi flight", kinds=["note"]) == []

    def test_the_source_is_labelled(self):
        f = _fabric(_goal("book the delhi flight"))
        assert f.recall("delhi flight")[0].source == "goal_system"


class TestFinishedGoalsNeverLeak:
    """A done goal reaching a planner is how an agent cheerfully re-books a
    flight the user already booked."""

    def test_a_done_goal_is_not_recalled(self):
        f = _fabric(_goal("book the delhi flight", state="done"))
        assert f.recall("delhi flight") == []

    def test_a_dropped_goal_is_not_recalled(self):
        f = _fabric(_goal("book the delhi flight", state="dropped"))
        assert f.recall("delhi flight") == []

    def test_an_open_goal_in_any_working_state_is_recalled(self):
        for state in ("captured", "planning", "acting", "blocked"):
            f = _fabric(_goal("book the delhi flight", state=state))
            assert f.recall("delhi flight"), state


class TestTheLineThePlannerSees:
    def test_a_plain_goal_reads_as_an_ongoing_goal(self):
        f = _fabric(_goal("book the delhi flight"))
        assert f.recall("delhi flight")[0].text == "ongoing goal: book the delhi flight"

    def test_a_blocked_goal_carries_its_blocker_and_question(self):
        """Both halves matter: what is wanted AND why it stalled — otherwise
        the model re-plans into the same wall."""
        g = _goal("book the delhi flight", state="blocked",
                  blocker="need_user", ask="which airline?")
        line = _fabric(g).recall("delhi flight")[0].text
        assert "blocked (need_user)" in line and "which airline?" in line

    def test_state_is_carried_in_meta_too(self):
        g = _goal("book the delhi flight", state="blocked", blocker="need_user")
        hit = _fabric(g).recall("delhi flight")[0]
        assert hit.meta["state"] == "blocked"
        assert hit.meta["blocker"] == "need_user"

    def test_it_reaches_the_agent_prompt_block(self):
        f = _fabric(_goal("book the delhi flight"))
        ctx = f.recall_context("delhi flight")
        assert "Relevant memory:" in ctx and "ongoing goal" in ctx


class TestRanking:
    def test_a_goal_outranks_an_equally_relevant_note(self):
        """A standing intention is more actionable than a lexically-similar
        old note — that is what the higher salience buys."""
        class _UM:
            _data = {"notes": [{"text": "book the delhi flight"}]}

        f = MemoryFabric(
            semantic_provider=lambda: None, kg_provider=lambda: None,
            user_memory_provider=lambda: _UM(),
            goal_provider=lambda: _Goals(_goal("book the delhi flight")),
            now_fn=lambda: 1_000_000.0)
        kinds = [h.kind for h in f.recall("book the delhi flight")]
        assert kinds.index("goal") < kinds.index("note")

    def test_a_fresher_goal_outranks_a_stale_one(self):
        now = 1_000_000.0
        old = _goal("delhi flight booking old", updated=now - 60 * 86400)
        new = _goal("delhi flight booking new", updated=now)
        hits = _fabric(old, new, now=now).recall("delhi flight booking")
        assert "new" in hits[0].text


class TestRobustness:
    def test_no_goal_store_is_silence_not_an_error(self):
        f = MemoryFabric(semantic_provider=lambda: None, kg_provider=lambda: None,
                         user_memory_provider=lambda: None,
                         goal_provider=lambda: None)
        assert f.recall("anything") == []

    def test_a_store_that_raises_is_survived(self):
        class _Boom:
            def open_goals(self):
                raise RuntimeError("goals file gone")

        f = MemoryFabric(semantic_provider=lambda: None, kg_provider=lambda: None,
                         user_memory_provider=lambda: None,
                         goal_provider=lambda: _Boom())
        assert f.recall("delhi flight") == []

    def test_one_malformed_goal_does_not_lose_the_others(self):
        class _Bad:
            is_open = True

            def __getattr__(self, name):
                raise RuntimeError("nope")

        class _Mixed:
            def open_goals(self):
                return [_Bad(), _goal("book the delhi flight")]

        f = MemoryFabric(semantic_provider=lambda: None, kg_provider=lambda: None,
                         user_memory_provider=lambda: None,
                         goal_provider=lambda: _Mixed())
        hits = f.recall("delhi flight")
        assert len(hits) == 1 and "delhi flight" in hits[0].text

    def test_a_goal_with_no_text_is_skipped(self):
        f = _fabric(_goal(""))
        assert f.recall("anything") == []


class TestWiring:
    def test_configure_accepts_a_goal_store(self):
        from core import memory_fabric as mf
        f = mf.configure(semantic=None, kg=None, user_memory=None,
                         goals=_Goals(_goal("book the delhi flight")))
        assert f.recall("delhi flight")

    def test_omitting_goals_still_works_for_existing_callers(self):
        """The three-argument call sites must keep working unchanged."""
        from core import memory_fabric as mf
        f = mf.configure(semantic=None, kg=None, user_memory=None)
        assert f is not None and f._goal_provider is mf._default_goals

    def test_goal_is_a_valid_kind(self):
        from core.memory_fabric import VALID_KINDS
        assert "goal" in VALID_KINDS


class TestStopwordFix:
    """`lexical_sim` used to count stopwords, so "what is the weather" and
    "book the delhi flight" overlapped on "the" and scored 0.25 — enough,
    once multiplied by a goal's 0.85 salience, to push an unrelated standing
    intention into a planner's context. Found by the test above."""

    def test_a_shared_stopword_is_not_a_match(self):
        from core.memory_fabric import lexical_sim
        assert lexical_sim("what is the weather",
                           "book the delhi flight") == 0.0

    def test_a_shared_content_word_still_matches(self):
        from core.memory_fabric import lexical_sim
        assert lexical_sim("delhi flight", "book the delhi flight") > 0.0

    def test_a_query_of_only_stopwords_matches_nothing(self):
        from core.memory_fabric import lexical_sim
        assert lexical_sim("what is the", "book the delhi flight") == 0.0

    def test_hinglish_fillers_are_stopwords_too(self):
        from core.memory_fabric import lexical_sim
        assert lexical_sim("ye kya hai", "wo kaam karo") == 0.0

    def test_it_still_ranks_by_how_much_of_the_query_is_covered(self):
        from core.memory_fabric import lexical_sim
        both = lexical_sim("delhi flight", "book the delhi flight")
        one = lexical_sim("delhi hotel", "book the delhi flight")
        assert both > one > 0.0
