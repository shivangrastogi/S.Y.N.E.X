"""Conversational state survives the brain process being replaced.

Fast lane: real DialogueState / ConversationHistory (both pure stdlib), no
engine, no spawn, no models.
"""

from __future__ import annotations

import time

from core.brain_snapshot import MAX_AGE_S, capture, is_empty, restore
from core.conversation import ConversationHistory
from core.dialogue_context import FRESH_WINDOW_S, DialogueState


class _Engine:
    """Just the three attributes the snapshot touches."""

    def __init__(self):
        self.dialogue = DialogueState()
        self.history = ConversationHistory(max_turns=8)
        self._pending_offer = None


def _talking_engine():
    e = _Engine()
    e.dialogue.note("open_app", {"app_name": "chrome"}, "chrome kholo",
                    "Chrome khol diya, sir.")
    e.history.add_user("chrome kholo")
    e.history.add_assistant("Chrome khol diya, sir.")
    return e


class TestCapture:
    def test_fresh_engine_carries_nothing(self):
        assert is_empty(capture(_Engine()))

    def test_captures_all_three_sections(self):
        e = _talking_engine()
        e._pending_offer = ("activate_mode", {"raw_text": "sleep mode"})
        snap = capture(e)
        assert set(snap) == {"v", "dialogue", "history", "offer"}
        assert not is_empty(snap)

    def test_ships_age_not_a_monotonic_timestamp(self):
        """The whole point: `ts` is process-local, so it must not travel."""
        snap = capture(_talking_engine())
        assert "ts" not in snap["dialogue"]
        assert snap["dialogue"]["age_s"] < 1.0

    def test_stale_dialogue_is_dropped(self):
        e = _talking_engine()
        e.dialogue.ts = time.monotonic() - (MAX_AGE_S + 60)
        assert "dialogue" not in capture(e)

    def test_garbage_engine_never_raises(self):
        class _Junk:
            dialogue = "not a state"
            history = 7

            @property
            def _pending_offer(self):
                raise RuntimeError("boom")

        assert is_empty(capture(_Junk()))


class TestRestore:
    def test_round_trip_resolves_the_follow_up(self):
        snap = capture(_talking_engine())
        fresh = _Engine()
        assert restore(fresh, snap) == ["dialogue", "history"]
        assert fresh.dialogue.last_intent == "open_app"
        assert fresh.dialogue.last_entities == {"app_name": "chrome"}
        # "ab isko band karo" now has something to resolve against.
        assert fresh.dialogue.fresh()

    def test_age_is_rebased_so_stale_stays_stale(self):
        """A turn from 5 minutes ago must not come back looking like 'just now'
        merely because the process restarted."""
        e = _talking_engine()
        e.dialogue.ts = time.monotonic() - (FRESH_WINDOW_S + 60)
        snap = capture(e)
        fresh = _Engine()
        assert restore(fresh, snap) == ["dialogue", "history"]
        assert fresh.dialogue.last_intent == "open_app"
        assert not fresh.dialogue.fresh()

    def test_a_wrong_process_clock_cannot_fake_freshness(self):
        """Restore rebases onto THIS process's clock, so the restored ts is
        always in the past relative to it — never a future timestamp that
        would keep `fresh()` true forever."""
        snap = capture(_talking_engine())
        snap["dialogue"]["age_s"] = 30.0
        fresh = _Engine()
        restore(fresh, snap)
        assert fresh.dialogue.ts <= time.monotonic()
        assert 29.0 <= (time.monotonic() - fresh.dialogue.ts) <= 31.0

    def test_history_is_refilled_in_place(self):
        """`core.conversation._ACTIVE` and the skills holding a reference must
        keep pointing at the live object, so the deque is refilled, not
        replaced."""
        snap = capture(_talking_engine())
        fresh = _Engine()
        buf_before = fresh.history._buf
        restore(fresh, snap)
        assert fresh.history._buf is buf_before
        assert fresh.history.last_user_text() == "chrome kholo"
        assert len(fresh.history) == 2

    def test_pending_offer_comes_back_unpackable(self):
        e = _talking_engine()
        e._pending_offer = ("activate_mode", {"raw_text": "sleep mode"})
        fresh = _Engine()
        assert "offer" in restore(fresh, capture(e))
        skill, slots = fresh._pending_offer      # the engine's "haan" gate does this
        assert skill == "activate_mode" and slots["raw_text"] == "sleep mode"

    def test_partial_snapshot_still_restores_what_survived(self):
        snap = capture(_talking_engine())
        snap["dialogue"] = {"nonsense": True}
        fresh = _Engine()
        assert restore(fresh, snap) == ["history"]
        assert fresh.dialogue.last_intent is None

    def test_junk_input_is_a_no_op(self):
        fresh = _Engine()
        assert restore(fresh, None) == []
        assert restore(fresh, "not a dict") == []
        assert restore(fresh, {"v": 1}) == []

    def test_newer_schema_restores_what_it_recognises(self):
        snap = capture(_talking_engine())
        snap["v"] = 99
        snap["telepathy"] = {"whatever": 1}
        assert restore(_Engine(), snap) == ["dialogue", "history"]

    def test_history_longer_than_this_builds_buffer_keeps_the_newest(self):
        """A snapshot from a build with a bigger buffer must not be rejected —
        the deque's own maxlen trims it, oldest first."""
        snap = {"v": 1, "history": {"turns": [
            {"role": "user" if i % 2 == 0 else "assistant",
             "content": f"t{i}", "timestamp": "", "sentiment": None}
            for i in range(30)]}}
        small = _Engine()                      # maxlen 16
        assert restore(small, snap) == ["history"]
        assert len(small.history) == small.history._buf.maxlen == 16
        assert small.history.last_user_text() == "t28"
