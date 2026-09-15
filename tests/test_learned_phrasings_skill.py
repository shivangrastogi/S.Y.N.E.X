"""The window onto what self-correction learned (§6.24).

Routing rewrites are only safe if the user can see and undo them, so this is
tested as carefully as the learning itself.
"""

from __future__ import annotations

import pytest

from core.repair_memory import RepairMemory, set_active
from skills.learned_phrasings_skill import learned_phrasings


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def mem():
    m = RepairMemory(path=None, clock=_Clock())
    set_active(m)
    yield m
    set_active(None)


def _teach(m, missed, repair, intent):
    m.note_turn(missed, ok=False)
    m.note_turn(repair, intent=intent, confidence=0.9, ok=True)


def _say(text):
    return learned_phrasings({"raw_text": text})


class TestOffAndEmpty:
    def test_no_engine_attached_says_so(self):
        set_active(None)
        assert "AERIS_REPAIR_MEMORY=1" in _say("kya seekha tumne")

    def test_nothing_learned_yet(self, mem):
        out = _say("what phrasings have you learned")
        assert "nahi seekhi" in out


class TestShow:
    def test_lists_what_was_learned(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        out = _say("learned phrasings")
        assert "chrome band karo" in out and "close_app" in out

    def test_most_used_first(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        _teach(mem, "gaana chalu karo", "play gaana", "play_music")
        for _ in range(3):
            mem.lookup("gaana chalu karo")
        out = _say("show learned phrasings")
        assert out.index("gaana chalu karo") < out.index("chrome band karo")

    def test_a_long_list_is_truncated_not_dumped(self, mem):
        for i in range(25):
            _teach(mem, f"alpha{chr(97+i)} wala kaam",
                   f"do alpha{chr(97+i)} wala", f"intent{i}")
        out = _say("learned phrasings")
        assert "aur" in out and out.count("•") == 15


class TestForget:
    def test_a_quoted_phrase_is_removed(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        out = _say('forget "chrome band karo" phrasing')
        assert "bhool gaya" in out and mem.lookup("chrome band karo") is None

    def test_an_unknown_quoted_phrase_says_so_and_keeps_the_rest(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        out = _say('forget "never taught this" phrasing')
        assert "nahi hai" in out and len(mem) == 1

    def test_a_bare_forget_drops_the_most_recent_lesson(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        out = _say("forget that phrasing")
        assert "bhool gaya" in out and len(mem) == 0

    def test_forget_all(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        _teach(mem, "gaana chalu karo", "play gaana", "play_music")
        out = _say("sab seekhi phrasings hata do")
        assert "2" in out and len(mem) == 0

    def test_forget_all_when_empty(self, mem):
        assert "kuch tha hi nahi" in _say("clear all learned phrasings")

    def test_bare_forget_with_nothing_recent_explains_the_quoted_form(self, mem):
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        mem.forget_last()
        out = _say("forget that phrasing")
        assert "quotes" in out

    def test_showing_is_not_forgetting(self, mem):
        """'kya seekha' must never be read as a removal."""
        _teach(mem, "chrome band karo", "close chrome", "close_app")
        _say("kya seekha tumne")
        assert len(mem) == 1


class TestRobustness:
    def test_a_broken_memory_does_not_break_the_turn(self):
        class _Boom:
            def __len__(self):
                raise RuntimeError("disk gone")

        set_active(_Boom())
        try:
            assert "dikkat" in _say("learned phrasings")
        finally:
            set_active(None)

    def test_missing_raw_text_is_handled(self, mem):
        assert learned_phrasings({}) is not None


class TestCorpusDiscipline:
    def test_it_registers_exactly_one_intent(self):
        """The routing audit blames 587-intent bloat for 50% accuracy, so
        show/forget/forget-all are sub-commands of ONE intent, not three."""
        from core.skill_registry import REGISTRY
        import skills.learned_phrasings_skill  # noqa: F401
        owned = [n for n in REGISTRY if "phrasing" in n or "learned" in n]
        assert owned == ["learned_phrasings"]

    def test_patterns_avoid_the_crowded_forget_space(self):
        """`kg_skill`, `preferences`, `custom_gestures_skill` and
        `conversation_recap` already own bare forget/bhool phrasings."""
        from core.skill_registry import REGISTRY
        import skills.learned_phrasings_skill  # noqa: F401
        for p in REGISTRY["learned_phrasings"].patterns:
            if "forget" in p or "bhool" in p or "unlearn" in p or "hata" in p:
                assert ("phrasing" in p or "seekhi" in p), p
