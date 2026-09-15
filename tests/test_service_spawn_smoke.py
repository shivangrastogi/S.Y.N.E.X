"""Do the vision and voice children actually come up?

Every seam test so far uses a fake proxy, so nothing checks the one thing that
has to work before any of it matters: that `vision_handler_factory` and
`voice_handler_factory` can be pickled by Windows `spawn`, constructed inside a
real child, and answer.

The distinction that matters here is **"answers no" versus "crash-loops"**. On
a machine with no MediaPipe, no camera or no microphone, the child must still
start and report the situation — `RemoteVision.enable()` turns that into a
reason for the user. If the factory raised during construction instead, the
bus's FATAL handshake would fire and the supervisor would keep respawning a
service that can never work.

Hardware-free by construction: `ping` and `status` are answered without opening
any device. Voice builds its STT and TTS lazily (§6.25 — speaking must not open
the microphone), and constructing `GestureEngine` loads MediaPipe's model but
does not claim the camera; only `start` does, and these tests never call it.

Slow lane — Windows `spawn` re-imports the suite per child.
"""

from __future__ import annotations

import pytest

from core.service_bus import ServiceProxy

pytestmark = pytest.mark.slow


def _spawn(name, factory, ready_timeout=120):
    p = ServiceProxy(name, factory)
    started = p.start(ready_timeout=ready_timeout)
    return p, started


class TestVoiceChild:
    def test_it_comes_up_and_answers(self):
        from core.voice_service import voice_handler_factory
        p, started = _spawn("voice", voice_handler_factory)
        try:
            assert started, "voice child failed to start"
            assert p.request("ping", {}, timeout=30).payload == {"pong": True}
        finally:
            p.stop()

    def test_it_reports_status_without_opening_any_device(self):
        """The laziness rule from §6.25, observed from outside the process."""
        from core.voice_service import voice_handler_factory
        p, started = _spawn("voice", voice_handler_factory)
        try:
            assert started
            s = p.request("status", {}, timeout=30).payload
            assert s["mic_open"] is False
            assert s["speaker_ready"] is False
            assert s["speaking"] is False
        finally:
            p.stop()

    def test_barge_in_on_a_silent_service_answers_no_rather_than_erroring(self):
        from core.voice_service import voice_handler_factory
        p, started = _spawn("voice", voice_handler_factory)
        try:
            assert started
            r = p.request("stop_speaking", {}, timeout=30)
            assert r.ok and r.payload["ok"] is False
        finally:
            p.stop()


class TestVisionChild:
    def test_it_comes_up_and_answers(self):
        from core.vision_service import vision_handler_factory
        p, started = _spawn("vision", vision_handler_factory)
        try:
            assert started, "vision child failed to start"
            assert p.request("ping", {}, timeout=30).payload == {"pong": True}
        finally:
            p.stop()

    def test_status_is_answerable_without_a_camera(self):
        from core.vision_service import vision_handler_factory
        p, started = _spawn("vision", vision_handler_factory)
        try:
            assert started
            s = p.request("status", {}, timeout=30).payload
            assert s["enabled"] is False
            assert isinstance(s["available"], bool)
        finally:
            p.stop()

    def test_a_machine_without_mediapipe_gets_a_reason_not_a_crash_loop(self):
        """`start` may legitimately refuse here (no camera on CI, no
        MediaPipe). What it must never do is take the child down — that would
        turn a configuration answer into a respawn loop."""
        from core.vision_service import vision_handler_factory
        p, started = _spawn("vision", vision_handler_factory)
        try:
            assert started
            r = p.request("start", {}, timeout=60)
            assert r.ok, f"start raised across the bus: {r.error}"
            assert isinstance(r.payload.get("ok"), bool)
            if not r.payload["ok"]:
                assert r.payload.get("reason") or r.payload.get("error")
            else:
                p.request("stop", {}, timeout=30)      # don't leave it holding the camera
            # Either way the child is still alive and answering.
            assert p.request("ping", {}, timeout=30).payload == {"pong": True}
        finally:
            p.stop()


class TestAllThreeFactoriesArePicklable:
    """The failure this catches is a `spawn`-only one: a factory that is not
    module-level imports fine and then dies inside the child."""

    @pytest.mark.parametrize("module,name", [
        ("core.brain_service", "brain_handler_factory"),
        ("core.vision_service", "vision_handler_factory"),
        ("core.voice_service", "voice_handler_factory"),
    ])
    def test_pickles_by_qualified_name(self, module, name):
        import importlib
        import pickle
        fn = getattr(importlib.import_module(module), name)
        assert pickle.loads(pickle.dumps(fn)) is fn
