"""Brain backend selector — flag parsing + both backends (fakes, no spawn)."""

from __future__ import annotations

from core.brain_backend import (
    use_split_brain, get_brain_backend, InProcessBackend,
)


class _FakeEngine:
    def __init__(self):
        self.last_dispatch = {"skill": "greet"}
        self.custom_marker = "engine-attr"
        self.spoke = []

    def process_text(self, text):
        return f"in:{text}"

    def _speak(self, text):
        self.spoke.append(text)


class _FakeRemote:
    def __init__(self):
        self.started = False

    def start(self, ready_timeout=0):
        self.started = True
        return True

    def is_ready(self):
        return self.started

    def process_text(self, text):
        return f"remote:{text}"

    def poll_events(self):
        return []


class TestFlag:
    def test_truthy_values(self):
        for v in ("1", "true", "TRUE", "yes", "on"):
            assert use_split_brain(v) is True

    def test_falsy_values(self):
        for v in ("", "0", "no", "off", None and ""):
            assert use_split_brain(v) is False


class TestSelection:
    def test_in_process_default(self):
        b = get_brain_backend(flag=False, engine_builder=_FakeEngine)
        assert isinstance(b, InProcessBackend)
        assert b.process_text("hi") == "in:hi"
        assert b.is_ready() and b.start() is True
        assert b.last_dispatch == {"skill": "greet"}
        assert b.poll_events() == []

    def test_in_process_delegates_other_attrs(self):
        b = get_brain_backend(flag=False, engine_builder=_FakeEngine)
        # transparent: engine-only attributes/methods still reachable
        assert b.custom_marker == "engine-attr"
        b._speak("hello")
        assert b._engine.spoke == ["hello"]

    def test_split_returns_remote(self):
        rem = _FakeRemote()
        b = get_brain_backend(flag=True, remote_builder=lambda: rem)
        assert b is rem
        assert b.process_text("hi") == "remote:hi"


class TestUniformSurface:
    def test_both_share_the_gui_surface(self):
        inproc = get_brain_backend(flag=False, engine_builder=_FakeEngine)
        remote = get_brain_backend(flag=True, remote_builder=_FakeRemote)
        for b in (inproc, remote):
            assert hasattr(b, "process_text")
            assert hasattr(b, "start")
            assert hasattr(b, "is_ready")
            assert hasattr(b, "poll_events")
