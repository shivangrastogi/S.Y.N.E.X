"""Local service bus — spawns REAL child processes to prove isolation works.

Uses module-level factories from core.service_bus so Windows 'spawn' can import
them cleanly (no test-module re-execution).
"""

from __future__ import annotations

import pytest

from core.service_bus import (
    ServiceProxy, echo_handler_factory, counting_handler_factory,
    bad_init_factory,
)


@pytest.fixture
def echo():
    p = ServiceProxy("echo", echo_handler_factory)
    assert p.start(ready_timeout=30), "echo service failed to start"
    yield p
    p.stop()


class TestRequestResponse:
    def test_echo_roundtrip(self, echo):
        r = echo.request("echo", {"text": "hello bus"}, timeout=10)
        assert r.ok and r.payload["text"] == "hello bus"

    def test_unknown_kind_soft_error(self, echo):
        r = echo.request("nope", {}, timeout=10)
        assert r.ok and "unknown kind" in r.payload.get("error", "")

    def test_handler_exception_becomes_error_reply(self, echo):
        r = echo.request("boom", {}, timeout=10)
        assert r.ok is False and "intentional failure" in r.error

    def test_alive(self, echo):
        assert echo.is_alive() and echo.is_ready()


class TestState:
    def test_child_keeps_its_own_state(self):
        p = ServiceProxy("counter", counting_handler_factory)
        assert p.start(ready_timeout=30)
        try:
            assert p.request("tick").payload["count"] == 1
            assert p.request("tick").payload["count"] == 2
            assert p.request("tick").payload["count"] == 3
        finally:
            p.stop()


class TestLifecycle:
    def test_bad_init_reports_failure(self):
        p = ServiceProxy("bad", bad_init_factory)
        assert p.start(ready_timeout=15) is False
        assert not p.is_ready()

    def test_stop_then_request_raises(self, echo):
        echo.stop()
        assert not echo.is_alive()
        with pytest.raises(RuntimeError):
            echo.request("echo", {"text": "x"}, timeout=5)

    def test_restart_recovers(self):
        p = ServiceProxy("echo2", echo_handler_factory)
        assert p.start(ready_timeout=30)
        try:
            assert p.request("echo", {"text": "a"}).payload["text"] == "a"
            assert p.restart(ready_timeout=30)
            assert p.request("echo", {"text": "b"}).payload["text"] == "b"
        finally:
            p.stop()


class TestEvents:
    def test_emit_aware_service_pushes_events(self):
        from core.service_bus import emitting_handler_factory
        p = ServiceProxy("emitter", emitting_handler_factory)
        assert p.start(ready_timeout=30)
        try:
            # request still works
            assert p.request("fire", {"text": "sleep mode karu?"}).payload["fired"]
            # and the unsolicited event arrives
            import time as _t
            evs = []
            for _ in range(20):
                evs = p.poll_events()
                if evs:
                    break
                _t.sleep(0.05)
            assert len(evs) == 1
            assert evs[0].kind == "event:offer"
            assert evs[0].payload["text"] == "sleep mode karu?"
        finally:
            p.stop()
