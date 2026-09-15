"""Do the real classes actually have what the process-isolation services call?

Born from a real bug (§6.25). `core/voice_service.py` called `tts.stop()`;
`core/tts.py` had no `stop()`. The unit tests passed anyway, because the test
fake *did* have one — so the suite was certifying an interface that did not
exist. Barge-in looked implemented and silently did nothing.

That is the failure mode every injected-dependency design invites: fakes let
you test the logic without the device, and nothing then checks that the fake
and the device agree. These tests are that check. They are deliberately
**interface-only** — no instantiation, no camera, no microphone, no models —
so they stay in the fast lane while still failing the moment a service starts
calling something the real class does not provide.

Modules whose imports need optional native deps (vosk, PyAudio, PyQt5) are
skipped rather than failed, so a machine missing them still runs the rest.
"""

from __future__ import annotations

import inspect

import pytest


def _requires(cls, *names):
    missing = [n for n in names if not callable(getattr(cls, n, None))]
    assert not missing, (
        f"{cls.__module__}.{cls.__name__} is missing {missing} — a service "
        f"calls these. Fakes in the unit tests may still define them, which "
        f"is exactly how this goes unnoticed.")


def _accepts(fn, *params):
    sig = inspect.signature(fn)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return
    missing = [p for p in params if p not in sig.parameters]
    assert not missing, f"{fn.__qualname__} does not accept {missing}"


class TestVoiceService:
    """`core/voice_service.py` → `core.tts.TTS` / `core.stt.STT`."""

    def test_tts_supports_barge_in(self):
        """THE regression. `stop()` and `is_speaking()` are what make
        interrupting playback possible at all."""
        tts = pytest.importorskip("core.tts")
        _requires(tts.TTS, "speak", "stop", "is_speaking")

    def test_tts_stop_reports_whether_it_interrupted_anything(self):
        """`SpeechPlayer.stop()` counts an interruption only on a truthy
        return, and `RemoteVoice.stop_speaking()` forwards it to the GUI."""
        tts = pytest.importorskip("core.tts")
        ret = inspect.signature(tts.TTS.stop).return_annotation
        assert ret in (bool, "bool"), (
            "TTS.stop() must report whether it actually stopped something")

    def test_stt_exposes_the_capture_call(self):
        stt = pytest.importorskip("core.stt")
        _requires(stt.STT, "listen")

    def test_stt_listen_honours_prefer_offline(self):
        """The SLEEPING privacy preference is only real if `listen` takes the
        flag. It did not, so the voice service computed `prefer_offline` and
        threw it away — the room's audio still went to Google to check for a
        wake word (§6.28)."""
        stt = pytest.importorskip("core.stt")
        _accepts(stt.STT.listen, "prefer_offline")

    def test_stt_exposes_streaming_with_the_partial_callback(self):
        """Opt-in live partials (§6.29) drive `listen_streaming(on_partial=…)`.
        The adapter degrades if it is absent, but if it exists the keyword has
        to be the one we pass."""
        stt = pytest.importorskip("core.stt")
        _requires(stt.STT, "listen_streaming")
        _accepts(stt.STT.listen_streaming, "on_partial")

    def test_the_service_only_calls_what_exists(self):
        """Names `voice_service` reaches for on the injected devices."""
        tts = pytest.importorskip("core.tts")
        for name in ("speak", "stop", "is_speaking"):
            assert hasattr(tts.TTS, name), name


class TestVisionService:
    """`core/vision_service.py` → `GestureEngine` / `VisionEngine`."""

    def test_gesture_engine_surface(self):
        ge = pytest.importorskip("core.gesture_engine")
        _requires(ge.GestureEngine, "is_available", "is_enabled", "start",
                  "stop", "add_listener", "set_cursor_mode", "is_cursor_mode")

    def test_is_available_is_backed_by_an_attribute_set_in_init(self):
        """`make_vision_handler`'s `start` calls `is_available()` directly,
        so an unset backing attribute would raise across the bus instead of
        answering 'no mediapipe'."""
        ge = pytest.importorskip("core.gesture_engine")
        src = inspect.getsource(ge.GestureEngine.__init__)
        assert "_mediapipe_ok" in src

    def test_vision_engine_snapshot_takes_a_timeout(self):
        ve = pytest.importorskip("core.vision_engine")
        _requires(ve.VisionEngine, "snapshot", "subscribe", "unsubscribe")
        _accepts(ve.VisionEngine.snapshot, "timeout")

    def test_the_singleton_getters_exist(self):
        ge = pytest.importorskip("core.gesture_engine")
        ve = pytest.importorskip("core.vision_engine")
        assert callable(ge.get_gesture_engine)
        assert callable(ve.get_vision_engine)


class TestBrainService:
    """`core/brain_service.py` + `core/brain_snapshot.py` → the engine."""

    def test_engine_exposes_process_text(self):
        me = pytest.importorskip("core.main_engine")
        _requires(me.JarvisMainEngine, "process_text")

    def test_the_snapshot_targets_still_exist_on_the_engine(self):
        """`brain_snapshot` lifts three attributes out of a live engine. They
        are set in `__init__`, so this checks the source rather than an
        instance — building one loads torch."""
        me = pytest.importorskip("core.main_engine")
        src = inspect.getsource(me.JarvisMainEngine.__init__)
        for attr in ("self.dialogue", "self.history", "self._pending_offer"):
            assert attr in src, f"{attr} is no longer set in __init__"

    def test_dialogue_and_history_have_the_shapes_snapshot_assumes(self):
        from core.conversation import ConversationHistory
        from core.dialogue_context import DialogueState
        d = DialogueState()
        for f in ("last_intent", "last_entities", "last_user_text",
                  "last_reply", "ts"):
            assert hasattr(d, f), f
        assert hasattr(ConversationHistory(max_turns=2), "_buf")


class TestGoalsInTheFabric:
    """`core/memory_fabric.py` → `core/goal_system.py`."""

    def test_the_store_exposes_open_goals(self):
        gs = pytest.importorskip("core.goal_system")
        _requires(gs.GoalStore, "open_goals")
        assert callable(gs.get_goal_store)

    def test_goal_carries_the_fields_the_planner_line_is_built_from(self):
        gs = pytest.importorskip("core.goal_system")
        fields = set(gs.Goal.__dataclass_fields__)
        assert {"text", "state", "blocker", "ask", "created",
                "updated"} <= fields

    def test_is_open_is_a_property_not_a_method(self):
        """`_recall_goals` filters on `store.open_goals()`, but the never-leak
        tests read `g.is_open` directly — a change to a method would make them
        silently truthy."""
        gs = pytest.importorskip("core.goal_system")
        assert isinstance(gs.Goal.is_open, property)


class TestServiceProxyContract:
    """Every seam (`RemoteBrain`, `RemoteVision`, `RemoteVoice`,
    `BrainHibernator`) drives a proxy through this surface."""

    def test_proxy_surface(self):
        from core.service_bus import ServiceProxy
        _requires(ServiceProxy, "start", "stop", "is_ready", "is_alive",
                  "restart", "request", "poll_events")

    def test_start_and_restart_take_a_ready_timeout(self):
        from core.service_bus import ServiceProxy
        _accepts(ServiceProxy.start, "ready_timeout")
        _accepts(ServiceProxy.restart, "ready_timeout")

    def test_supervisor_supports_the_hibernator_handshake(self):
        from core.service_supervisor import Supervisor
        _requires(Supervisor, "suspend", "resume", "is_suspended")


class TestHandlerFactoriesArePicklable:
    """Windows spawn pickles the factory by qualified name, so every one must
    be module-level and emit-aware."""

    @pytest.mark.parametrize("module,name", [
        ("core.brain_service", "brain_handler_factory"),
        ("core.vision_service", "vision_handler_factory"),
        ("core.voice_service", "voice_handler_factory"),
    ])
    def test_factory(self, module, name):
        mod = pytest.importorskip(module)
        fn = getattr(mod, name)
        assert fn.__module__ == module and fn.__qualname__ == name
        assert "emit" in inspect.signature(fn).parameters
