"""The voice cutover adapter (§6.31) — fake RemoteVoice, no mic, no spawn.

Like the gesture adapter, the last test re-derives from the source what
`VoiceWorker` actually consumes, so the cutover cannot silently rot.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytest.importorskip("PyQt5.QtCore")

from core.remote_voice import VoicePoll                       # noqa: E402
from core.remote_voice_engine import (                        # noqa: E402
    RemoteVoiceEngine, split_voice_enabled,
)
from core.voice_modes import ACTIVE, SLEEPING, STOPPED        # noqa: E402


class _FakeVoice:
    def __init__(self, listen_ok=True):
        self.listen_ok = listen_ok
        self.listens = 0
        self.mutes = 0
        self.shutdowns = 0
        self.queue: list = []
        self.last_error = ""
        self.boom = False

    def listen(self, state=ACTIVE):
        self.listens += 1
        if not self.listen_ok:
            self.last_error = "no microphone"
            return False
        return True

    def mute(self):
        self.mutes += 1
        return True

    def shutdown(self):
        self.shutdowns += 1

    def poll(self):
        if self.boom:
            raise RuntimeError("service gone")
        return self.queue.pop(0) if self.queue else VoicePoll([], None, [])


def _eng(**kw):
    v = _FakeVoice(**kw)
    return RemoteVoiceEngine(voice=v), v


def _collect(engine):
    """Record every signal the GUI connects to."""
    got = {"captured": [], "state": [], "woke": 0, "slept": 0,
           "error": [], "started": 0, "partial": []}
    engine.captured.connect(got["captured"].append)
    engine.state_changed.connect(got["state"].append)
    engine.wake_detected.connect(lambda: got.__setitem__("woke", got["woke"] + 1))
    engine.sleep_detected.connect(lambda: got.__setitem__("slept", got["slept"] + 1))
    engine.error.connect(got["error"].append)
    engine.listening_started.connect(
        lambda: got.__setitem__("started", got["started"] + 1))
    engine.partial.connect(got["partial"].append)
    return got


class TestLifecycle:
    def test_initialize_does_not_open_the_microphone(self):
        """Mirrors `ContinuousVoiceEngine.initialize`, and §6.25's rule that
        nothing opens the mic until someone asks to listen."""
        e, v = _eng()
        e.initialize()
        assert v.listens == 0

    def test_start_listening_opens_it_and_announces(self):
        e, v = _eng()
        got = _collect(e)
        e.start_listening()
        assert v.listens == 1 and got["started"] == 1
        assert got["state"] == [ACTIVE]

    def test_a_refusal_surfaces_as_the_error_signal(self):
        e, v = _eng(listen_ok=False)
        got = _collect(e)
        e.start_listening()
        assert got["started"] == 0 and got["error"] == ["no microphone"]

    def test_stop_listening_mutes_and_reports_stopped(self):
        e, v = _eng()
        got = _collect(e)
        e.start_listening()
        e.stop_listening()
        assert v.mutes == 1 and got["state"] == [ACTIVE, STOPPED]

    def test_shutdown_kills_the_child(self):
        e, v = _eng()
        e.start_listening()
        e.shutdown()
        assert v.shutdowns == 1


class TestSignalMapping:
    def test_transcripts_become_captured(self):
        e, v = _eng()
        got = _collect(e)
        v.queue = [VoicePoll(["chrome kholo", "gaana chalao"], None, [])]
        assert e.drain_once() == 2
        assert got["captured"] == ["chrome kholo", "gaana chalao"]

    def test_a_state_change_is_announced_once(self):
        e, v = _eng()
        got = _collect(e)
        v.queue = [VoicePoll([], SLEEPING, []), VoicePoll([], SLEEPING, [])]
        e.drain_once()
        e.drain_once()
        assert got["state"] == [SLEEPING]        # not repeated

    def test_wake_and_sleep_are_derived_from_transitions(self):
        """Derived rather than read from the service's own woke/slept events,
        because `poll()` collapses state to the last edge in a batch."""
        e, v = _eng()
        got = _collect(e)
        v.queue = [VoicePoll([], ACTIVE, []), VoicePoll([], SLEEPING, []),
                   VoicePoll([], ACTIVE, [])]
        for _ in range(3):
            e.drain_once()
        assert got["slept"] == 1 and got["woke"] == 1
        assert got["state"] == [ACTIVE, SLEEPING, ACTIVE]

    def test_stopped_to_active_is_not_a_wake(self):
        """Starting to listen is not the same event as waking from sleep."""
        e, v = _eng()
        got = _collect(e)
        v.queue = [VoicePoll([], ACTIVE, [])]
        e.drain_once()
        assert got["woke"] == 0 and got["state"] == [ACTIVE]

    def test_partials_are_emitted_separately_from_finals(self):
        e, v = _eng()
        got = _collect(e)
        v.queue = [VoicePoll(["chrome kholo"], None, ["chro", "chrome"])]
        e.drain_once()
        assert got["partial"] == ["chro", "chrome"]
        assert got["captured"] == ["chrome kholo"]

    def test_a_failing_poll_is_survived(self):
        e, v = _eng()
        v.boom = True
        assert e.drain_once() == 0

    def test_draining_before_initialize_is_harmless(self):
        e = RemoteVoiceEngine(voice=None)
        assert e.drain_once() == 0


class TestFlag:
    def test_off_by_default(self):
        assert split_voice_enabled({}) is False
        assert split_voice_enabled({"AERIS_SPLIT_VOICE": "0"}) is False

    def test_on_when_asked(self):
        for v in ("1", "true", "YES", "on"):
            assert split_voice_enabled({"AERIS_SPLIT_VOICE": v}) is True

    def test_the_factory_returns_the_in_process_engine_by_default(
            self, monkeypatch):
        """The GUI one-liner is only safe if this is provably unchanged with
        the flag off — same class, same object."""
        monkeypatch.delenv("AERIS_SPLIT_VOICE", raising=False)
        import core.voice_engine as ve

        class _Sentinel:
            def __init__(self, parent=None):
                self.parent = parent

        monkeypatch.setattr(ve, "ContinuousVoiceEngine", _Sentinel)
        assert isinstance(ve.make_voice_engine(None), _Sentinel)

    def test_the_flag_swaps_the_factory(self, monkeypatch):
        monkeypatch.setenv("AERIS_SPLIT_VOICE", "1")
        import core.voice_engine as ve
        assert isinstance(ve.make_voice_engine(None), RemoteVoiceEngine)

    def test_a_broken_split_falls_back_rather_than_losing_the_mic(
            self, monkeypatch):
        monkeypatch.setenv("AERIS_SPLIT_VOICE", "1")
        import core.voice_engine as ve
        import core.remote_voice_engine as rve

        class _Sentinel:
            def __init__(self, parent=None):
                pass

        def _boom(*a, **k):
            raise RuntimeError("no bus")

        monkeypatch.setattr(rve, "RemoteVoiceEngine", _boom)
        monkeypatch.setattr(ve, "ContinuousVoiceEngine", _Sentinel)
        assert isinstance(ve.make_voice_engine(None), _Sentinel)


class TestTheAdapterCoversWhatVoiceWorkerUses:
    """Re-derived from the source — the same guard the gesture adapter has."""

    @staticmethod
    def _surface() -> set:
        from tests.surface_probe import engine_surface
        root = pathlib.Path(__file__).resolve().parents[1]
        return engine_surface(root, ("ui",),
                              r"make_voice_engine\(|ContinuousVoiceEngine\(")

    def test_every_signal_and_slot_the_gui_uses_exists(self):
        surface = self._surface()
        assert surface, "surface detection found nothing — the regex broke"
        missing = [n for n in surface if not hasattr(RemoteVoiceEngine, n)]
        assert not missing, (
            f"RemoteVoiceEngine is missing {missing}, which VoiceWorker uses "
            f"on the real engine. Split mode would lose them.")

    def test_the_surface_is_what_we_scoped(self):
        assert self._surface() == {
            "captured", "error", "initialize", "listening_started",
            "sleep_detected", "state_changed", "wake_detected"}

    def test_the_worker_also_calls_start_and_stop_listening(self):
        """Reached through `self._engine`, so the binder regex above can't see
        them — pinned explicitly rather than left uncovered."""
        for name in ("start_listening", "stop_listening"):
            assert callable(getattr(RemoteVoiceEngine, name, None)), name
