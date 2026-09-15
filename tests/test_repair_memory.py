"""In-session self-correction — learning a phrasing from a rephrase.

Precision-first, so most of these tests are about what it REFUSES to learn.
Pure logic: no engine, no models, injected clock, tmp_path for persistence.
"""

from __future__ import annotations

from core.repair_memory import (
    RepairMemory, content_tokens, is_correction_marker, learnable, related,
)


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _mem(**kw):
    c = _Clock()
    kw.setdefault("path", None)
    return RepairMemory(clock=c, **kw), c


def _miss_then_hit(mem, missed="chrome band karo", repair="close chrome",
                   intent="close_app", conf=0.9):
    mem.note_turn(missed, ok=False)
    return mem.note_turn(repair, intent=intent, confidence=conf, ok=True)


class TestTheHappyPath:
    def test_a_rephrase_teaches_the_failed_phrasing(self):
        mem, _ = _mem()
        assert _miss_then_hit(mem) == "chrome band karo"
        a = mem.lookup("chrome band karo")
        assert a is not None and a.intent == "close_app"

    def test_lookup_is_normalised_not_literal(self):
        """The router normalises before matching, so the table has to agree —
        otherwise it misses on exactly the shorthand the normaliser folds."""
        mem, _ = _mem()
        _miss_then_hit(mem)
        assert mem.lookup("  Chrome BAND karo!! ") is not None

    def test_hits_are_counted(self):
        mem, _ = _mem()
        _miss_then_hit(mem)
        mem.lookup("chrome band karo")
        mem.lookup("chrome band karo")
        assert mem.lookup("chrome band karo").hits == 3

    def test_slots_can_be_attached_so_a_repeat_reproduces_the_action(self):
        mem, _ = _mem()
        phrase = _miss_then_hit(mem)
        mem.remember_slots(phrase, {"app_name": "chrome"})
        assert mem.lookup(phrase).slots == {"app_name": "chrome"}

    def test_an_unknown_phrase_is_simply_unknown(self):
        mem, _ = _mem()
        assert mem.lookup("kuch bhi") is None


class TestWhatItRefusesToLearn:
    """A wrong alias reroutes a phrase forever — strictly worse than the miss
    it replaced. Every one of these is a deliberate decline."""

    def test_an_unrelated_next_command_is_not_a_repair(self):
        mem, _ = _mem()
        mem.note_turn("chrome band karo", ok=False)
        mem.note_turn("aaj ka mausam batao", intent="weather",
                      confidence=0.95, ok=True)
        assert mem.lookup("chrome band karo") is None and mem.declined == 1

    def test_a_late_rephrase_is_a_new_topic(self):
        mem, c = _mem()
        mem.note_turn("chrome band karo", ok=False)
        c.advance(600)
        mem.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        assert mem.lookup("chrome band karo") is None

    def test_a_low_confidence_repair_teaches_nothing(self):
        mem, _ = _mem()
        assert _miss_then_hit(mem, conf=0.4) is None
        assert mem.lookup("chrome band karo") is None

    def test_a_successful_turn_after_a_successful_turn_is_not_a_repair(self):
        mem, _ = _mem()
        mem.note_turn("open chrome", intent="open_app", confidence=0.9, ok=True)
        mem.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        assert len(mem) == 0

    def test_phrases_with_digits_are_declined(self):
        """'remind me at 4 30' is a one-off, and '2 plus 2 → calculate' would
        be useless next time the user says '5 plus 7'."""
        mem, _ = _mem()
        mem.note_turn("yaad dila do char baje 30", ok=False)
        mem.note_turn("set a reminder", intent="reminder", confidence=0.9, ok=True)
        assert len(mem) == 0

    def test_one_word_phrases_are_too_ambiguous(self):
        mem, _ = _mem()
        mem.note_turn("chrome", ok=False)
        mem.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        assert len(mem) == 0

    def test_long_utterances_are_not_phrasings(self):
        mem, _ = _mem()
        mem.note_turn("please could you kindly go ahead and shut the browser "
                      "window down for me thanks", ok=False)
        mem.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        assert len(mem) == 0

    def test_the_same_phrase_repeated_is_not_a_rephrase(self):
        mem, _ = _mem()
        mem.note_turn("close chrome", ok=False)
        mem.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        assert len(mem) == 0

    def test_filler_overlap_alone_does_not_make_two_phrases_related(self):
        """'karo'/'do' appear everywhere; relatedness has to mean content."""
        mem, _ = _mem()
        mem.note_turn("gaana chala do", ok=False)
        mem.note_turn("screenshot le karo", intent="screenshot",
                      confidence=0.95, ok=True)
        assert len(mem) == 0


class TestExplicitCorrection:
    def test_galat_buys_back_the_relatedness_requirement(self):
        """A translation-style rephrase shares no token, so it is declined —
        unless the user told us it was wrong."""
        mem, _ = _mem()
        mem.note_turn("mausam kaisa hai", ok=False)
        mem.note_turn("galat")
        mem.note_turn("weather batao", intent="weather", confidence=0.9, ok=True)
        assert mem.lookup("mausam kaisa hai").source == "explicit"

    def test_without_galat_the_same_pair_is_declined(self):
        mem, _ = _mem()
        mem.note_turn("mausam kaisa hai", ok=False)
        mem.note_turn("weather batao", intent="weather", confidence=0.9, ok=True)
        assert mem.lookup("mausam kaisa hai") is None

    def test_the_correction_word_does_not_become_the_pending_miss(self):
        """'galat' must not overwrite the miss it is complaining about."""
        mem, _ = _mem()
        mem.note_turn("mausam kaisa hai", ok=False)
        mem.note_turn("galat")
        mem.note_turn("weather batao", intent="weather", confidence=0.9, ok=True)
        assert mem.lookup("galat") is None
        assert mem.lookup("mausam kaisa hai") is not None

    def test_correction_markers(self):
        for w in ("galat", "wrong", "nahi", "GALAT HAI", " undo "):
            assert is_correction_marker(w), w
        for w in ("that was the wrong file", "chrome band karo", ""):
            assert not is_correction_marker(w), w


class TestSelfRepair:
    def test_an_alias_that_leads_to_a_miss_deletes_itself(self):
        mem, _ = _mem()
        _miss_then_hit(mem)
        assert mem.lookup("chrome band karo") is not None
        mem.note_turn("chrome band karo", ok=False, from_alias=True)
        assert mem.lookup("chrome band karo") is None and mem.forgotten == 1

    def test_galat_after_an_alias_turn_drops_it(self):
        mem, _ = _mem()
        _miss_then_hit(mem)
        mem.note_turn("chrome band karo", ok=False, from_alias=True)
        assert len(mem) == 0

    def test_forget_last_undoes_the_most_recent_lesson(self):
        mem, _ = _mem()
        _miss_then_hit(mem)
        assert mem.forget_last() == "chrome band karo"
        assert len(mem) == 0 and mem.forget_last() is None

    def test_forget_an_unknown_phrase_is_false_not_an_error(self):
        mem, _ = _mem()
        assert mem.forget("never taught") is False

    def test_clear(self):
        mem, _ = _mem()
        _miss_then_hit(mem)
        mem.clear()
        assert len(mem) == 0


class TestBounds:
    def test_the_table_is_capped_and_evicts_the_least_recently_used(self):
        mem, c = _mem(max_aliases=3)
        for i in range(5):
            mem.note_turn(f"phrase{chr(97+i)} band karo", ok=False)
            mem.note_turn(f"close appx{chr(97+i)} band", intent=f"i{i}",
                          confidence=0.9, ok=True)
            c.advance(1)
        assert len(mem) == 3

    def test_a_used_alias_outlives_one_that_was_never_repeated(self):
        mem, c = _mem(max_aliases=2)
        mem.note_turn("alpha wala kaam", ok=False)
        mem.note_turn("do alpha wala", intent="a", confidence=0.9, ok=True)
        c.advance(1)
        mem.note_turn("beta wala kaam", ok=False)
        mem.note_turn("do beta wala", intent="b", confidence=0.9, ok=True)
        c.advance(1)
        mem.lookup("alpha wala kaam")          # keep alpha warm
        c.advance(1)
        mem.note_turn("gamma wala kaam", ok=False)
        mem.note_turn("do gamma wala", intent="g", confidence=0.9, ok=True)
        assert mem.lookup("alpha wala kaam") is not None
        assert mem.lookup("beta wala kaam") is None

    def test_stats(self):
        mem, _ = _mem()
        _miss_then_hit(mem)
        s = mem.stats()
        assert s["aliases"] == 1 and s["learned"] == 1


class TestPersistence:
    def test_round_trip(self, tmp_path):
        p = str(tmp_path / "repair.json")
        m1 = RepairMemory(path=p, clock=_Clock())
        m1.note_turn("chrome band karo", ok=False)
        m1.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        m1.remember_slots("chrome band karo", {"app_name": "chrome"})

        m2 = RepairMemory(path=p, clock=_Clock())
        a = m2.lookup("chrome band karo")
        assert a.intent == "close_app" and a.slots == {"app_name": "chrome"}

    def test_a_missing_file_is_an_empty_table(self, tmp_path):
        m = RepairMemory(path=str(tmp_path / "nope.json"))
        assert len(m) == 0

    def test_corrupt_json_does_not_raise(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert len(RepairMemory(path=str(p))) == 0

    def test_one_bad_row_does_not_lose_the_table(self, tmp_path):
        p = tmp_path / "part.json"
        p.write_text('{"v":1,"aliases":{"good one":{"intent":"x"},'
                     '"bad one":{"nope":1},"third one":"notadict"}}',
                     encoding="utf-8")
        m = RepairMemory(path=str(p))
        assert len(m) == 1 and m.lookup("good one").intent == "x"

    def test_saving_creates_the_parent_directory(self, tmp_path):
        p = str(tmp_path / "nested" / "deep" / "repair.json")
        m = RepairMemory(path=p, clock=_Clock())
        m.note_turn("chrome band karo", ok=False)
        m.note_turn("close chrome", intent="close_app", confidence=0.9, ok=True)
        assert RepairMemory(path=p).lookup("chrome band karo") is not None


class TestHelpers:
    def test_content_tokens_drop_filler_and_short_words(self):
        assert content_tokens("chrome band karo please") == {"chrome", "band"}

    def test_related(self):
        assert related("chrome band karo", "close chrome")
        assert not related("chrome band karo", "aaj ka mausam")

    def test_learnable(self):
        assert learnable("chrome band karo")
        assert not learnable("chrome")            # one content word
        assert not learnable("call at 430")       # digits
        assert not learnable("galat")             # a correction marker
        assert not learnable("")


class TestEngineWiring:
    """`JarvisMainEngine._note_repair_turn` against a stub — the method only
    touches four attributes, so this exercises the real wiring without
    building a brain (import is 0.4 s and pulls in no torch)."""

    def _stub(self, dispatch=None, from_alias=False, slots=None):
        from core.main_engine import JarvisMainEngine

        class _S:
            pass

        s = _S()
        s.repair = RepairMemory(path=None, clock=_Clock())
        s.last_dispatch = dispatch
        s._turn_from_alias = from_alias
        if slots is not None:
            s._turn_slots = slots
        return s, JarvisMainEngine._note_repair_turn

    def _dispatch(self, ts, intent="close_app", conf=0.9, action="executed"):
        return {"ts": ts, "intent": intent, "confidence": conf, "action": action}

    def test_a_real_repair_is_learned_through_the_engine_seam(self):
        s, note = self._stub()
        note(s, "chrome band karo", 100.0)                    # miss: no dispatch
        s.last_dispatch = self._dispatch(ts=200.0)
        note(s, "close chrome", 150.0)
        assert s.repair.lookup("chrome band karo").intent == "close_app"

    def test_a_stale_dispatch_does_not_count_as_success(self):
        """`last_dispatch` is never cleared by the engine — only by its
        callers — so a chat turn can still be carrying the PREVIOUS turn's
        dispatch. Trusting it would teach the alias backwards."""
        s, note = self._stub()
        stale = self._dispatch(ts=100.0)                      # before the turn
        s.last_dispatch = stale
        note(s, "chrome band karo", 150.0)                    # must read as a MISS
        s.last_dispatch = self._dispatch(ts=200.0)
        note(s, "close chrome", 160.0)
        assert s.repair.lookup("chrome band karo") is not None

    def test_a_stale_dispatch_cannot_fabricate_a_repair(self):
        s, note = self._stub()
        note(s, "chrome band karo", 100.0)
        s.last_dispatch = self._dispatch(ts=50.0)             # stale
        note(s, "close chrome", 150.0)
        assert s.repair.lookup("chrome band karo") is None

    def test_an_asked_slot_turn_is_not_a_success(self):
        s, note = self._stub()
        note(s, "chrome band karo", 100.0)
        s.last_dispatch = self._dispatch(ts=200.0, action="asked_slot")
        note(s, "close chrome", 150.0)
        assert s.repair.lookup("chrome band karo") is None

    def test_slots_are_attached_from_the_side_channel(self):
        s, note = self._stub(slots={"app_name": "chrome"})
        note(s, "chrome band karo", 100.0)
        s.last_dispatch = self._dispatch(ts=200.0)
        note(s, "close chrome", 150.0)
        assert s.repair.lookup("chrome band karo").slots == {"app_name": "chrome"}

    def test_an_alias_turn_that_missed_forgets_itself(self):
        s, note = self._stub()
        note(s, "chrome band karo", 100.0)
        s.last_dispatch = self._dispatch(ts=200.0)
        note(s, "close chrome", 150.0)
        assert s.repair.lookup("chrome band karo") is not None
        s.last_dispatch = None
        s._turn_from_alias = True
        note(s, "chrome band karo", 300.0)
        assert s.repair.lookup("chrome band karo") is None

    def test_a_raising_repair_memory_never_costs_the_user_their_reply(self):
        s, note = self._stub()

        class _Boom:
            def note_turn(self, *a, **k):
                raise RuntimeError("disk full")

        s.repair = _Boom()
        note(s, "chrome band karo", 100.0)          # must not raise
