"""Wake/sleep policy, extracted Qt-free so the voice service can share it.

These pin the semantics copied from `ContinuousVoiceEngine._loop` — including
the pre-existing substring behaviour, which is preserved on purpose.
"""

from __future__ import annotations

from core import voice_modes as vm
from core.voice_modes import ACTIVE, SLEEPING, STOPPED, decide


class TestTriggers:
    def test_wake_words(self):
        for t in ("ok jarvis", "hey aeris", "wake up", "jaag jao", "activate"):
            assert vm.is_wake_trigger(t), t

    def test_sleep_words(self):
        for t in ("jarvis sleep", "go to sleep", "standby", "sleep mode"):
            assert vm.is_sleep_trigger(t), t

    def test_case_and_whitespace_insensitive(self):
        assert vm.is_wake_trigger("   OK Jarvis   ")

    def test_matching_is_substring_as_it_always_was(self):
        """Pre-existing behaviour, preserved deliberately: a wake word inside
        a longer sentence still counts. Tightening it is a UX decision about a
        hand-tuned voice flow, not part of this refactor."""
        assert vm.is_wake_trigger("ok jarvis kya haal hai")
        assert vm.is_wake_trigger("i had to wake up early today")

    def test_unrelated_speech_is_neither(self):
        assert not vm.is_wake_trigger("chrome band karo")
        assert not vm.is_sleep_trigger("chrome band karo")


class TestDecide:
    def test_active_speech_is_delivered(self):
        d = decide(ACTIVE, "chrome band karo")
        assert d.deliver and d.state == ACTIVE and d.event is None

    def test_sleeping_swallows_everything_but_a_wake_word(self):
        """The silence is the feature — a sleeping AERIS must not act."""
        d = decide(SLEEPING, "chrome band karo")
        assert not d.deliver and d.state == SLEEPING and d.event is None

    def test_a_wake_word_wakes_it_and_is_not_itself_a_command(self):
        d = decide(SLEEPING, "ok jarvis")
        assert d.state == ACTIVE and d.event == "woke" and not d.deliver

    def test_a_sleep_word_is_consumed_not_executed(self):
        d = decide(ACTIVE, "go to sleep")
        assert d.state == SLEEPING and d.event == "slept" and not d.deliver

    def test_stopped_stays_stopped(self):
        assert decide(STOPPED, "ok jarvis").state == STOPPED

    def test_empty_speech_changes_nothing(self):
        for state in (ACTIVE, SLEEPING, STOPPED):
            d = decide(state, "   ")
            assert d.state == state and not d.deliver

    def test_an_unknown_state_is_treated_as_active_not_raised(self):
        """This runs on the capture thread; raising costs the user their mic."""
        d = decide("WEIRD", "chrome band karo")
        assert d.deliver and d.state == ACTIVE


class TestPrivacy:
    def test_sleeping_transcribes_offline(self):
        """A sleeping AERIS is still hearing the room, so that audio must not
        leave the machine just to check for 'wake up'."""
        assert vm.prefer_offline(SLEEPING) is True

    def test_active_may_use_the_online_recogniser(self):
        assert vm.prefer_offline(ACTIVE) is False


class TestBackCompat:
    def test_voice_engine_still_exports_the_original_names(self):
        """`voice_engine` re-exports rather than redefining, so there is one
        source of truth and no importer had to change."""
        pytest = __import__("pytest")
        pyqt = pytest.importorskip("PyQt5.QtCore")   # skip where Qt is absent
        assert pyqt is not None
        from core import voice_engine as ve
        assert ve.WAKE_TRIGGERS is vm.WAKE_TRIGGERS
        assert ve.SLEEP_TRIGGERS is vm.SLEEP_TRIGGERS
        assert (ve.ACTIVE, ve.SLEEPING, ve.STOPPED) == (ACTIVE, SLEEPING, STOPPED)
