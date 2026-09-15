"""Voice service contract + capture loop — scripted fake microphone.

No PyAudio, no models, no sound card, no sleeping. The point of injecting
``listen_once`` is that the whole wake/sleep/deliver behaviour is exercised
deterministically.
"""

from __future__ import annotations

import threading
import time

from core.voice_modes import ACTIVE, SLEEPING, STOPPED
from core.voice_service import VoiceLoop, make_voice_handler, voice_handler_factory


class _Mic:
    """Returns scripted transcripts, then silence forever."""

    def __init__(self, *lines):
        self.lines = list(lines)
        self.offline_calls = []

    def __call__(self, offline):
        self.offline_calls.append(offline)
        return self.lines.pop(0) if self.lines else ""


class _Speaker:
    """Mirrors the real `core.tts.TTS` barge-in contract: `speak()` blocks for
    the length of the utterance, `is_speaking()` reports it, and `stop()`
    returns whether it actually interrupted something."""

    def __init__(self):
        self.said = []
        self.stopped = 0
        self.boom = False
        self._speaking = threading.Event()
        self._interrupt = threading.Event()
        self.hold = False           # block in speak() until stopped

    def speak(self, text):
        if self.boom:
            raise RuntimeError("no audio device")
        self._interrupt.clear()
        self._speaking.set()
        try:
            self.said.append(text)
            if self.hold:
                self._interrupt.wait(5.0)
        finally:
            self._speaking.clear()

    def is_speaking(self):
        return self._speaking.is_set()

    def stop(self):
        if not self._speaking.is_set():
            return False
        self.stopped += 1
        self._interrupt.set()
        return True


def _loop(*lines, state=ACTIVE):
    events = []
    lp = VoiceLoop(_Mic(*lines), emit=lambda k, p: events.append((k, p)))
    lp.state = state
    return lp, events


class TestCaptureLoop:
    def test_active_speech_is_returned_and_published(self):
        lp, events = _loop("chrome band karo")
        assert lp.step() == "chrome band karo"
        assert ("transcript", {"text": "chrome band karo",
                               "state": ACTIVE}) in events

    def test_silence_yields_nothing(self):
        lp, events = _loop("")
        assert lp.step() is None and events == []

    def test_sleeping_swallows_speech(self):
        lp, events = _loop("chrome band karo", state=SLEEPING)
        assert lp.step() is None
        assert not any(k == "transcript" for k, _ in events)

    def test_a_wake_word_flips_state_and_announces_it(self):
        lp, events = _loop("ok jarvis", state=SLEEPING)
        assert lp.step() is None
        assert lp.state == ACTIVE
        kinds = [k for k, _ in events]
        assert "voice_state" in kinds and "voice_woke" in kinds

    def test_a_sleep_word_is_not_delivered_as_a_command(self):
        lp, events = _loop("go to sleep")
        assert lp.step() is None and lp.state == SLEEPING
        assert "voice_slept" in [k for k, _ in events]

    def test_while_asleep_it_transcribes_offline(self):
        """Privacy, not speed: a sleeping mic's audio must not leave the box."""
        mic = _Mic("chrome band karo")
        lp = VoiceLoop(mic)
        lp.state = SLEEPING
        lp.step()
        assert mic.offline_calls == [True]

    def test_while_active_the_online_recogniser_is_allowed(self):
        mic = _Mic("chrome band karo")
        lp = VoiceLoop(mic)
        lp.state = ACTIVE
        lp.step()
        assert mic.offline_calls == [False]

    def test_a_capture_error_is_counted_not_raised(self):
        seen = []

        def _boom(offline):
            raise OSError("device unplugged")

        lp = VoiceLoop(_boom, on_error=seen.append)
        assert lp.step() is None and lp.errors == 1 and seen

    def test_an_emit_that_raises_cannot_break_capture(self):
        def _boom(kind, payload):
            raise RuntimeError("bus closed")

        lp = VoiceLoop(_Mic("chrome band karo"), emit=_boom)
        lp.state = ACTIVE          # a fresh loop is STOPPED, which delivers nothing
        assert lp.step() == "chrome band karo"     # still delivered

    def test_counts(self):
        lp, _ = _loop("one two", "three four")
        lp.step()
        lp.step()
        assert lp.transcripts == 2


class TestHandler:
    def _h(self, mic=None, speaker=None, emit=None):
        sp = speaker or _Speaker()
        lp = VoiceLoop(mic or _Mic(), emit=emit)
        return make_voice_handler(tts_builder=lambda: sp, emit=emit, loop=lp), sp, lp

    def test_ping(self):
        h, _, _ = self._h()
        assert h("ping", {}) == {"pong": True}

    def test_speak(self):
        h, sp, _ = self._h()
        assert h("speak", {"text": "namaste"})["ok"] is True
        _settle(lambda: sp.said == ["namaste"])
        assert sp.said == ["namaste"]

    def test_speaking_nothing_is_refused_cleanly(self):
        h, sp, _ = self._h()
        assert h("speak", {"text": "  "})["ok"] is False and sp.said == []

    def test_a_dead_sound_card_is_reported_asynchronously(self):
        """`speak` returns when playback STARTS, so a device failure can no
        longer come back in that reply — it surfaces on the player instead.
        The alternative (blocking until the audio finishes) is what made
        barge-in impossible, so this is the right trade."""
        sp = _Speaker()
        sp.boom = True
        h, _, _ = self._h(speaker=sp)
        assert h("speak", {"text": "hi"})["ok"] is True
        _settle(lambda: sp.said == [] and not sp.is_speaking())
        assert h("status", {})["speaking"] is False

    def test_barge_in_stops_playback(self):
        sp = _Speaker()
        sp.hold = True                       # a long utterance, still playing
        h, _, _ = self._h(speaker=sp)
        h("speak", {"text": "a long sentence"})
        _settle(sp.is_speaking)
        assert h("stop_speaking", {})["ok"] is True and sp.stopped == 1

    def test_speaking_does_not_block_the_service_loop(self):
        """`_service_loop` is single-threaded: a blocking speak would park the
        whole service for the length of the utterance — and the request that
        arrives during an utterance is the one meant to interrupt it."""
        sp = _Speaker()
        sp.hold = True
        h, _, _ = self._h(speaker=sp)
        h("speak", {"text": "a very long sentence"})
        _settle(sp.is_speaking)
        assert h("ping", {}) == {"pong": True}      # still answerable
        assert h("status", {})["speaking"] is True
        h("stop_speaking", {})

    def test_a_new_utterance_supersedes_the_one_in_flight(self):
        """Two voices at once is never what was wanted."""
        sp = _Speaker()
        sp.hold = True
        h, _, _ = self._h(speaker=sp)
        h("speak", {"text": "first"})
        _settle(sp.is_speaking)
        h("speak", {"text": "second"})
        _settle(lambda: sp.said == ["first", "second"])
        assert sp.stopped == 1
        h("stop_speaking", {})

    def test_barge_in_before_anything_was_said_is_clean(self):
        h, _, _ = self._h()
        assert h("stop_speaking", {})["ok"] is False

    def test_status_before_listening(self):
        h, _, _ = self._h()
        s = h("status", {})
        assert s["state"] == STOPPED and s["listening"] is False

    def test_set_state_from_the_parent(self):
        h, _, lp = self._h()
        assert h("set_state", {"state": SLEEPING})["state"] == SLEEPING
        assert lp.state == SLEEPING

    def test_listen_stop_is_safe_before_start(self):
        h, _, _ = self._h()
        assert h("listen_stop", {})["ok"] is True

    def test_unknown_kind(self):
        h, _, _ = self._h()
        assert "unknown" in h("weird", {})["error"]


class TestLaziness:
    def test_speaking_does_not_open_the_microphone(self):
        """A child spawned only to read a reply out must not switch the mic
        on — that is a privacy cost, not just a resource one."""
        opened = []

        def _stt():
            opened.append(1)
            return object()

        h = make_voice_handler(stt_builder=_stt,
                               tts_builder=lambda: _Speaker(),
                               loop=VoiceLoop(_Mic()))
        h("speak", {"text": "namaste"})
        assert opened == []
        assert h("status", {})["mic_open"] is False


class TestFactory:
    def test_it_is_top_level_and_emit_aware(self):
        """Windows spawn pickles the factory by qualified name."""
        import inspect
        assert voice_handler_factory.__module__ == "core.voice_service"
        assert "emit" in inspect.signature(voice_handler_factory).parameters

    def test_the_module_pulls_in_no_qt_and_no_audio_stack(self):
        """The whole point of the extraction: the service must be importable
        in a child that has no PyQt5 — and must not open audio libraries just
        by being imported. Checked in a clean interpreter, because this
        process has already imported Qt via other tests."""
        import subprocess
        import sys
        code = ("import sys, core.voice_service, core.voice_modes;"
                "bad=[m for m in sys.modules if m.split('.')[0] in "
                "('PyQt5','pyaudio','speech_recognition','vosk','pygame')];"
                "print(sorted(set(m.split('.')[0] for m in bad)))")
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True, timeout=180)
        assert out.stdout.strip() == "[]", out.stdout + out.stderr


def _settle(pred, timeout=3.0):
    """Wait for a background speak thread to reach a state. Only used where a
    real thread is genuinely involved; the policy logic stays synchronous."""
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.005)
    return False


class TestBargeIn:
    """Mic and speaker share this process precisely so the user talking over
    AERIS is decided here, with no IPC (§6.25)."""

    def _wired(self, *lines, speaking=True):
        sp = _Speaker()
        events = []
        lp = VoiceLoop(_Mic(*lines), emit=lambda k, p: events.append((k, p)),
                       is_speaking=lambda: speaking, interrupt=sp.stop)
        lp.state = ACTIVE
        sp._speaking.set() if speaking else None
        return lp, sp, events

    def test_speech_while_speaking_interrupts_it(self):
        lp, sp, events = self._wired("ruko ruko")
        lp.step()
        assert sp.stopped == 1 and lp.barge_ins == 1
        assert "barge_in" in [k for k, _ in events]

    def test_the_interrupting_words_are_still_delivered(self):
        """"ruko, gaana chala do" should both stop the speech AND run."""
        lp, sp, _ = self._wired("gaana chala do")
        assert lp.step() == "gaana chala do"

    def test_nothing_is_interrupted_when_aeris_is_silent(self):
        lp, sp, events = self._wired("chrome band karo", speaking=False)
        lp.step()
        assert sp.stopped == 0 and lp.barge_ins == 0
        assert "barge_in" not in [k for k, _ in events]

    def test_silence_never_barges_in(self):
        lp, sp, _ = self._wired("")
        lp.step()
        assert sp.stopped == 0 and lp.barge_ins == 0

    def test_barge_in_works_while_asleep_too(self):
        """Talking over AERIS means "stop talking" even when the words will be
        discarded by the sleep policy."""
        lp, sp, _ = self._wired("kuch bhi")
        lp.state = SLEEPING
        assert lp.step() is None          # not delivered, as designed
        assert sp.stopped == 1            # but it did shut up

    def test_an_interrupt_that_raises_does_not_kill_capture(self):
        def _boom():
            raise RuntimeError("mixer gone")

        lp = VoiceLoop(_Mic("ruko"), is_speaking=lambda: True, interrupt=_boom)
        lp.state = ACTIVE
        assert lp.step() == "ruko"        # still delivered

    def test_no_barge_in_wiring_is_simply_inert(self):
        lp = VoiceLoop(_Mic("ruko"))
        lp.state = ACTIVE
        assert lp.step() == "ruko" and lp.barge_ins == 0


class TestOfflinePreferenceIsActuallyForwarded:
    """The SLEEPING privacy preference is only real if it reaches `STT.listen`.

    `VoiceLoop` computed `prefer_offline` correctly from the start, but the
    adapter dropped it — so a sleeping AERIS still shipped the room's audio to
    Google to check for a wake word. Signature checks alone would not have
    caught that; this exercises the forwarding (§6.28).
    """

    class _STT:
        def __init__(self):
            self.calls = []

        def listen(self, prefer_offline=False):
            self.calls.append(prefer_offline)
            return "kuch bola"

    def test_the_flag_reaches_the_recogniser(self):
        from core.voice_service import stt_listen
        s = self._STT()
        stt_listen(s, True)
        stt_listen(s, False)
        assert s.calls == [True, False]

    def test_an_old_stt_without_the_parameter_still_works(self):
        from core.voice_service import stt_listen

        class _Old:
            def __init__(self):
                self.calls = 0

            def listen(self):
                self.calls += 1
                return "kuch bola"

        old = _Old()
        assert stt_listen(old, True) == "kuch bola" and old.calls == 1

    def test_a_recogniser_without_listen_is_silence_not_a_crash(self):
        from core.voice_service import stt_listen
        assert stt_listen(object(), True) == ""

    def test_none_is_normalised_to_empty_string(self):
        from core.voice_service import stt_listen

        class _Quiet:
            def listen(self, prefer_offline=False):
                return None

        assert stt_listen(_Quiet(), True) == ""

    def test_end_to_end_a_sleeping_loop_asks_for_offline(self):
        from core.voice_service import stt_listen
        s = self._STT()
        lp = VoiceLoop(lambda offline: stt_listen(s, offline))
        lp.state = SLEEPING
        lp.step()
        assert s.calls == [True]
        lp.state = ACTIVE
        lp.step()
        assert s.calls == [True, False]


class TestStreamingPartials:
    """Opt-in live partials (`AERIS_VOICE_STREAMING`).

    Off by default for a reason about the MODELS, not the plumbing:
    `STT.listen_streaming` is Vosk end-to-end, so its final never reaches
    Google en-IN — the hand-picked Hinglish recogniser. That is a decision
    about a tuned stack, so it is the user's to make.
    """

    def _streaming_loop(self, *partials, final="chrome band karo",
                        state=ACTIVE):
        events = []

        def _stream(on_partial):
            for p in partials:
                on_partial(p)
            return final

        lp = VoiceLoop(_Mic(), emit=lambda k, p: events.append((k, p)),
                       listen_streaming=_stream)
        lp.state = state
        return lp, events

    def test_partials_are_published_as_they_arrive(self):
        lp, events = self._streaming_loop("chrome", "chrome band")
        lp.step()
        partials = [p["text"] for k, p in events if k == "partial"]
        assert partials == ["chrome", "chrome band"] and lp.partials == 2

    def test_the_final_is_still_the_thing_delivered(self):
        """A partial is an unfinished sentence — acting on half of one is
        worse than waiting."""
        lp, events = self._streaming_loop("chrome", "chrome band")
        assert lp.step() == "chrome band karo"
        assert ("transcript", {"text": "chrome band karo",
                               "state": ACTIVE}) in events

    def test_empty_partials_are_ignored(self):
        lp, _ = self._streaming_loop("", "   ", "chrome")
        lp.step()
        assert lp.partials == 1

    def test_no_partials_leak_while_asleep(self):
        """A sleeping AERIS showing a running transcript of the room is the
        same privacy leak as §6.28 in a different coat."""
        lp, events = self._streaming_loop("kuch", "kuch bhi", state=SLEEPING)
        lp.step()
        assert lp.partials == 0
        assert not any(k == "partial" for k, _ in events)

    def test_streaming_replaces_the_normal_capture_call(self):
        """Running both would capture the same utterance twice."""
        mic = _Mic("should not be used")
        lp = VoiceLoop(mic, listen_streaming=lambda on_partial: "streamed")
        lp.state = ACTIVE
        assert lp.step() == "streamed" and mic.offline_calls == []

    def test_a_streaming_failure_is_counted_like_any_capture_error(self):
        def _boom(on_partial):
            raise OSError("no pyaudio")

        lp = VoiceLoop(_Mic(), listen_streaming=_boom)
        lp.state = ACTIVE
        assert lp.step() is None and lp.errors == 1

    def test_off_by_default(self):
        from core.voice_service import streaming_enabled
        assert streaming_enabled({}) is False
        assert streaming_enabled({"AERIS_VOICE_STREAMING": "0"}) is False
        assert streaming_enabled({"AERIS_VOICE_STREAMING": "maybe"}) is False

    def test_the_flag_turns_it_on(self):
        from core.voice_service import streaming_enabled
        for v in ("1", "true", "YES", "on"):
            assert streaming_enabled({"AERIS_VOICE_STREAMING": v}) is True

    def test_the_adapter_degrades_when_the_recogniser_cannot_stream(self):
        from core.voice_service import stt_listen_streaming

        class _NoStream:
            def listen(self, prefer_offline=False):
                return "fell back"

        seen = []
        assert stt_listen_streaming(_NoStream(), seen.append) == "fell back"
        assert seen == []

    def test_the_adapter_forwards_partials(self):
        from core.voice_service import stt_listen_streaming

        class _Streams:
            def listen_streaming(self, on_partial=None, **kw):
                on_partial("half")
                return "whole"

        seen = []
        assert stt_listen_streaming(_Streams(), seen.append) == "whole"
        assert seen == ["half"]
