"""RemoteVoice seam + the live harness loop — fake proxy, no spawn.

The rule this file exists to protect: **speaking must never open the
microphone.** Speech and capture share a child process (they must, for
zero-IPC barge-in), but they are not the same permission.
"""

from __future__ import annotations

from core.bus_events import payloads, texts
from core.remote_voice import (
    RemoteVoice, VoicePoll, extract_partials, extract_transcripts,
    extract_voice_state,
)
from core.service_bus import Msg
from core.voice_modes import ACTIVE, SLEEPING, STOPPED


class _FakeProxy:
    def __init__(self, ready=False, start_ok=True):
        self._ready = ready
        self._alive = ready
        self.start_ok = start_ok
        self.starts = 0
        self.stops = 0
        self.calls = []
        self.events = []
        self.mode = "ok"              # ok | raise | error
        self.listening = False

    def start(self, ready_timeout=0):
        self.starts += 1
        self._ready = self._alive = self.start_ok
        return self.start_ok

    def stop(self, timeout=0):
        self.stops += 1
        self._ready = self._alive = False

    def is_ready(self):
        return self._ready

    def is_alive(self):
        return self._alive

    def request(self, kind, payload=None, timeout=0):
        self.calls.append(kind)
        if self.mode == "raise":
            raise TimeoutError("voice down")
        if self.mode == "error":
            return Msg(kind=kind, id="1", ok=False, error="boom")
        if kind == "listen_start":
            self.listening = True
            return Msg(kind=kind, id="1", ok=True,
                       payload={"ok": True, "state": ACTIVE})
        if kind == "listen_stop":
            self.listening = False
            return Msg(kind=kind, id="2", ok=True, payload={"ok": True})
        if kind == "status":
            return Msg(kind=kind, id="3", ok=True,
                       payload={"state": ACTIVE if self.listening else STOPPED,
                                "listening": self.listening,
                                "mic_open": self.listening})
        if kind == "set_state":
            return Msg(kind=kind, id="4", ok=True,
                       payload={"ok": True,
                                "state": (payload or {}).get("state")})
        return Msg(kind=kind, id="5", ok=True, payload={"ok": True})

    def poll_events(self):
        out, self.events = self.events, []
        return out


class TestExtract:
    def test_transcripts_in_order(self):
        evs = [Msg(kind="event:transcript", payload={"text": "chrome kholo"}),
               Msg(kind="event:gesture", payload={"name": "palm"}),
               Msg(kind="event:transcript", payload={"text": "gaana chalao"})]
        assert extract_transcripts(evs) == ["chrome kholo", "gaana chalao"]

    def test_malformed_events_are_skipped(self):
        evs = [Msg(kind="event:transcript", payload=None),
               Msg(kind="event:transcript", payload={"text": "  "}),
               {"kind": "event:transcript", "payload": {"text": "haan"}},
               None]
        assert extract_transcripts(evs) == ["haan"]

    def test_state_takes_the_last_edge_not_all_of_them(self):
        """A GUI polling slowly enough to see WOKE then SLEPT should render
        sleeping, not flash through both."""
        evs = [Msg(kind="event:voice_state", payload={"state": ACTIVE}),
               Msg(kind="event:voice_state", payload={"state": SLEEPING})]
        assert extract_voice_state(evs) == SLEEPING

    def test_no_state_events_means_none(self):
        assert extract_voice_state([]) is None


class TestSpeakingDoesNotListen:
    def test_speak_spawns_the_child_but_not_the_mic(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        assert rv.speak("namaste") is True
        assert p.starts == 1
        assert "listen_start" not in p.calls
        assert rv.status()["mic_open"] is False

    def test_listening_is_a_separate_deliberate_call(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv.speak("namaste")
        assert rv.listen() is True
        assert "listen_start" in p.calls and rv.status()["mic_open"] is True

    def test_mute_closes_the_mic_but_keeps_speech_working(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv.listen()
        assert rv.mute() is True
        assert rv.status()["mic_open"] is False
        assert rv.speak("phir bhi bol sakta hoon") is True
        assert p.stops == 0                 # child still alive

    def test_speaking_nothing_is_refused_without_spawning(self):
        p = _FakeProxy()
        assert RemoteVoice(proxy=p).speak("   ") is False
        assert p.starts == 0


class TestLifecycle:
    def test_shutdown_kills_the_child(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv.listen()
        rv.shutdown()
        assert p.stops == 1 and rv.is_running() is False

    def test_shutdown_before_anything_started_is_a_no_op(self):
        p = _FakeProxy()
        RemoteVoice(proxy=p).shutdown()
        assert p.stops == 0 and p.calls == []

    def test_the_child_is_spawned_once(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv.speak("a")
        rv.listen()
        rv.speak("b")
        assert p.starts == 1

    def test_set_state(self):
        rv = RemoteVoice(proxy=_FakeProxy())
        rv.listen()
        assert rv.set_state(SLEEPING) == SLEEPING
        assert rv.set_state("NONSENSE") is None

    def test_mute_when_nothing_is_running(self):
        assert RemoteVoice(proxy=_FakeProxy()).mute() is True


class TestDegradation:
    def test_a_child_that_will_not_come_up(self):
        rv = RemoteVoice(proxy=_FakeProxy(start_ok=False))
        assert rv.speak("hi") is False and rv.last_error

    def test_a_service_that_does_not_answer(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv._ensure_child()
        p.mode = "raise"
        assert rv.speak("hi") is False and rv.last_error

    def test_an_error_reply_is_reported(self):
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv._ensure_child()
        p.mode = "error"
        assert rv.speak("hi") is False and "boom" in rv.last_error

    def test_status_and_poll_when_nothing_runs(self):
        rv = RemoteVoice(proxy=_FakeProxy())
        assert rv.status()["running"] is False
        assert rv.poll() == ([], None, [])

    def test_barge_in_on_a_dead_service_is_false_not_an_error(self):
        assert RemoteVoice(proxy=_FakeProxy()).stop_speaking() is False


class TestPolling:
    def test_one_drain_returns_every_signal(self):
        """Separate poll methods would mean whichever ran second saw an empty
        queue and silently lost the others' events — which is why this is a
        named tuple rather than a method per signal."""
        p = _FakeProxy()
        rv = RemoteVoice(proxy=p)
        rv.listen()
        p.events = [Msg(kind="event:voice_state", payload={"state": SLEEPING}),
                    Msg(kind="event:partial", payload={"text": "ok jar"}),
                    Msg(kind="event:transcript", payload={"text": "ok jarvis"})]
        got = rv.poll()
        assert got.transcripts == ["ok jarvis"]
        assert got.state == SLEEPING
        assert got.partials == ["ok jar"]
        assert rv.poll() == ([], None, [])       # drained

    def test_partials_are_extracted_separately_from_finals(self):
        evs = [Msg(kind="event:partial", payload={"text": "chro"}),
               Msg(kind="event:transcript", payload={"text": "chrome kholo"})]
        assert extract_partials(evs) == ["chro"]
        assert extract_transcripts(evs) == ["chrome kholo"]


class TestSharedExtractor:
    """`core/bus_events.py` — the three seams share one tolerant reader."""

    def test_bare_and_prefixed_kinds_both_match(self):
        assert texts([Msg(kind="transcript", payload={"text": "a"}),
                      Msg(kind="event:transcript", payload={"text": "b"})],
                     "transcript") == ["a", "b"]

    def test_non_dict_payloads_are_skipped(self):
        assert payloads([Msg(kind="event:x", payload="nope")], "x") == []

    def test_the_other_two_seams_still_work_through_it(self):
        from core.remote_brain import extract_offers
        from core.remote_vision import extract_gestures
        assert extract_gestures(
            [Msg(kind="event:gesture", payload={"name": "palm"})]) == ["palm"]
        assert extract_offers(
            [Msg(kind="event:offer", payload={"text": "chai?"})])[0][0] == "chai?"


class TestHarness:
    def test_watch_prints_state_and_transcripts(self):
        from run_voice_split import watch

        class _V:
            def __init__(self):
                self.batches = [
                    VoicePoll(["chrome kholo"], ACTIVE, ["chro"]),
                    VoicePoll([], None, []),
                    VoicePoll(["gaana chalao"], SLEEPING, []),
                ]

            def poll(self):
                return (self.batches.pop(0) if self.batches
                        else VoicePoll([], None, []))

        out = []
        ticks = [0]

        def _stop():
            ticks[0] += 1
            return ticks[0] > 3

        n = watch(_V(), out.append, _stop, sleep_fn=lambda s: None)
        assert n == 2
        assert "  you said: chrome kholo" in out
        assert f"  [state] {SLEEPING}" in out
        assert any(o.endswith("chro") for o in out)    # partial shown live

    def test_watch_stops_immediately_when_asked(self):
        from run_voice_split import watch

        class _V:
            def poll(self):
                raise AssertionError("should not poll")

        assert watch(_V(), print, lambda: True, sleep_fn=lambda s: None) == 0
