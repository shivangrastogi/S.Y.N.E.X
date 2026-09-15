"""In-process subsystem supervision (P0 crash-isolation).

Fast by construction: the registry takes an injectable clock, so every
backoff assertion advances a fake clock instead of sleeping. No Qt, no
processes, no I/O.
"""

from __future__ import annotations

import threading

import pytest

from core.subsystem_registry import (
    SubsystemRegistry,
    SubsystemState,
    get_registry,
    reset_registry,
)


class _Clock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def reg(clock: _Clock) -> SubsystemRegistry:
    return SubsystemRegistry(clock=clock)


def _boom(msg: str = "nope"):
    def _install():
        raise RuntimeError(msg)
    return _install


class TestFaultIsolation:
    def test_install_failure_never_propagates(self, reg):
        reg.register("tray", _boom("no system tray"))
        assert reg.boot("tray") is False          # returns, does not raise
        assert reg.get("tray").state is SubsystemState.FAILED

    def test_one_failure_does_not_block_the_rest(self, reg):
        ran = []
        reg.register("a", lambda: ran.append("a"))
        reg.register("b", _boom())
        reg.register("c", lambda: ran.append("c"))
        results = reg.boot_all()
        assert ran == ["a", "c"]                  # c ran despite b dying
        assert results == {"a": True, "b": False, "c": True}

    def test_failure_is_remembered(self, reg):
        reg.register("bridge", _boom("network unreachable"))
        reg.boot("bridge")
        rec = reg.get("bridge")
        assert "network unreachable" in rec.last_error
        assert "RuntimeError" in rec.last_error
        assert "Traceback" in rec.last_traceback   # kept for support logs

    def test_unregistered_boot_is_a_no_op(self, reg):
        assert reg.boot("ghost") is False

    def test_boot_order_is_registration_order(self, reg):
        ran = []
        for n in ("z", "a", "m"):
            reg.register(n, lambda n=n: ran.append(n))
        reg.boot_all()
        assert ran == ["z", "a", "m"]


class TestRetryBudget:
    def test_default_is_one_attempt_no_retry(self, reg, clock):
        reg.register("hotkey", _boom())
        reg.boot("hotkey")
        assert reg.get("hotkey").state is SubsystemState.FAILED
        clock.advance(10_000)
        assert reg.due_for_retry() == []          # never comes back

    def test_retries_are_bounded_then_it_gives_up(self, reg, clock):
        attempts = []
        reg.register("health", lambda: attempts.append(1) or (_ for _ in ()).throw(
            RuntimeError("port busy")), max_retries=2, backoff_s=5.0)
        reg.boot("health")
        for _ in range(5):                        # far more ticks than budget
            clock.advance(1000)
            reg.retry_due()
        # 1 initial + exactly 2 retries, then left alone.
        assert len(attempts) == 3
        assert reg.get("health").state is SubsystemState.FAILED

    def test_backoff_gates_the_retry(self, reg, clock):
        reg.register("health", _boom(), max_retries=3, backoff_s=5.0)
        reg.boot("health")
        assert reg.due_for_retry() == []          # too early
        clock.advance(4.9)
        assert reg.due_for_retry() == []
        clock.advance(0.2)                        # now past 5.0
        assert reg.due_for_retry() == ["health"]

    def test_backoff_doubles(self, reg, clock):
        reg.register("health", _boom(), max_retries=3, backoff_s=5.0)
        reg.boot("health")
        first = reg.get("health").next_retry_at
        assert first == pytest.approx(5.0)
        clock.advance(5.0)
        reg.retry_due()                           # attempt 2 fails
        # second wait is 10s from t=5.0
        assert reg.get("health").next_retry_at == pytest.approx(15.0)

    def test_backoff_is_capped(self, reg, clock):
        reg.register("x", _boom(), max_retries=40, backoff_s=5.0)
        reg.boot("x")
        for _ in range(20):
            clock.advance(100_000)
            reg.retry_due()
        rec = reg.get("x")
        assert rec.next_retry_at - clock.t <= 300.0 + 1e-6


class TestRecovery:
    def test_a_flaky_subsystem_recovers(self, reg, clock):
        state = {"fail": True}

        def flaky():
            if state["fail"]:
                raise OSError("mic busy")

        reg.register("voice", flaky, max_retries=3, backoff_s=5.0)
        assert reg.boot("voice") is False
        state["fail"] = False                     # mic freed up
        clock.advance(6.0)
        assert reg.retry_due() == {"voice": True}
        rec = reg.get("voice")
        assert rec.state is SubsystemState.OK
        assert rec.last_error == ""               # history cleared on success
        assert rec.next_retry_at == 0.0

    def test_recovered_subsystem_can_fail_again_with_fresh_budget(
            self, reg, clock):
        """A subsystem that recovers still spends its budget; the budget is
        per-session, not per-outage. `reset` is the manual override."""
        reg.register("voice", lambda: None, max_retries=1, backoff_s=5.0)
        reg.boot("voice")
        reg.mark_degraded("voice", "mic lost")
        clock.advance(6.0)
        assert reg.retry_due() == {"voice": True}
        assert reg.get("voice").state is SubsystemState.OK

    def test_reset_clears_history(self, reg, clock):
        reg.register("tray", _boom())
        reg.boot("tray")
        assert reg.get("tray").state is SubsystemState.FAILED
        reg.reset("tray")
        rec = reg.get("tray")
        assert rec.state is SubsystemState.PENDING
        assert rec.attempts == 0
        assert rec.last_error == ""


class TestDegraded:
    def test_degraded_is_distinct_from_failed(self, reg):
        reg.register("voice", lambda: None, max_retries=2)
        reg.boot("voice")
        reg.mark_degraded("voice", "mic disappeared")
        rec = reg.get("voice")
        assert rec.state is SubsystemState.DEGRADED
        assert rec.state is not SubsystemState.FAILED
        assert "mic disappeared" in rec.last_error

    def test_degraded_schedules_a_reconnect(self, reg, clock):
        reg.register("bridge", lambda: None, max_retries=2, backoff_s=5.0)
        reg.boot("bridge")
        reg.mark_degraded("bridge", "socket closed")
        assert reg.due_for_retry() == []
        clock.advance(6.0)
        assert reg.due_for_retry() == ["bridge"]

    def test_degraded_without_budget_does_not_schedule(self, reg, clock):
        reg.register("bridge", lambda: None, max_retries=0)
        reg.boot("bridge")
        reg.mark_degraded("bridge", "socket closed")
        clock.advance(10_000)
        assert reg.due_for_retry() == []

    def test_mark_degraded_on_unknown_is_a_no_op(self, reg):
        reg.mark_degraded("ghost", "whatever")    # must not raise

    def test_reconnect_tears_down_first(self, reg):
        order = []
        reg.register(
            "voice",
            lambda: order.append("install"),
            teardown=lambda: order.append("teardown"),
            max_retries=1,
        )
        reg.boot("voice")
        reg.reconnect("voice")
        assert order == ["install", "teardown", "install"]

    def test_failing_teardown_does_not_block_reinstall(self, reg):
        installed = []

        def bad_teardown():
            raise RuntimeError("handle already closed")

        reg.register("voice", lambda: installed.append(1),
                     teardown=bad_teardown, max_retries=1)
        reg.boot("voice")
        assert reg.reconnect("voice") is True     # cleanup mess is ignored
        assert len(installed) == 2


class TestDisabled:
    def test_disabled_is_not_a_fault_and_is_never_retried(self, reg, clock):
        reg.register("voice", _boom(), max_retries=5, backoff_s=1.0)
        reg.mark_disabled("voice", "mic toggle off")
        assert reg.boot("voice") is False         # refuses to run
        clock.advance(10_000)
        assert reg.due_for_retry() == []
        assert reg.get("voice").state is SubsystemState.DISABLED

    def test_disabled_does_not_count_as_critical_down(self, reg):
        reg.register("voice", lambda: None, critical=True)
        reg.mark_disabled("voice", "user turned it off")
        snap = reg.snapshot()
        assert snap["critical_down"] == []
        assert snap["ok"] is True

    def test_enable_restores_pending(self, reg):
        reg.register("voice", lambda: None)
        reg.mark_disabled("voice")
        reg.enable("voice")
        assert reg.get("voice").state is SubsystemState.PENDING
        assert reg.boot("voice") is True

    def test_reconnect_refuses_a_disabled_subsystem(self, reg):
        ran = []
        reg.register("voice", lambda: ran.append(1))
        reg.mark_disabled("voice")
        assert reg.reconnect("voice") is False
        assert ran == []


class TestSnapshot:
    def test_snapshot_is_json_safe(self, reg):
        import json
        reg.register("a", lambda: None)
        reg.register("b", _boom())
        reg.boot_all()
        json.dumps(reg.snapshot())                # must not raise

    def test_snapshot_rolls_up(self, reg):
        reg.register("a", lambda: None)
        reg.register("b", _boom())
        reg.register("c", lambda: None, max_retries=2)
        reg.boot_all()
        reg.mark_degraded("c", "flaky")
        snap = reg.snapshot()
        assert snap["total"] == 3
        assert snap["healthy"] == 1
        assert snap["failed"] == ["b"]
        assert snap["degraded"] == ["c"]
        assert snap["ok"] is False

    def test_snapshot_ok_when_everything_is_up(self, reg):
        reg.register("a", lambda: None)
        reg.boot_all()
        assert reg.snapshot()["ok"] is True

    def test_retrying_counts_as_down(self, reg):
        """`ok` must never be True next to a non-empty `down` list — a
        subsystem mid-reconnect is not installed."""
        reg.register("a", _boom(), max_retries=3)
        reg.boot_all()
        snap = reg.snapshot()
        assert snap["degraded"] == ["a"]
        assert snap["ok"] is False

    def test_disabled_alone_is_still_ok(self, reg):
        reg.register("a", lambda: None)
        reg.register("voice", lambda: None)
        reg.boot("a")
        reg.mark_disabled("voice", "mic off")
        assert reg.snapshot()["ok"] is True

    def test_critical_failure_flips_ok(self, reg):
        reg.register("brain", _boom(), critical=True)
        reg.boot_all()
        snap = reg.snapshot()
        assert snap["critical_down"] == ["brain"]
        assert snap["ok"] is False

    def test_pending_critical_counts_as_down(self, reg):
        """Registered-but-never-booted critical subsystem is not 'ok'."""
        reg.register("brain", lambda: None, critical=True)
        assert reg.snapshot()["ok"] is False

    def test_summary_line_mentions_the_broken_ones(self, reg):
        reg.register("a", lambda: None)
        reg.register("tray", _boom())
        reg.register("voice", lambda: None, max_retries=2)
        reg.boot_all()
        reg.mark_degraded("voice", "mic lost")
        line = reg.summary_line()
        assert "1/3 subsystems up" in line
        assert "tray" in line and "voice" in line

    def test_snapshot_preserves_registration_order(self, reg):
        for n in ("z", "a", "m"):
            reg.register(n, lambda: None)
        assert [s["name"] for s in reg.snapshot()["subsystems"]] == \
            ["z", "a", "m"]


class TestRegistration:
    def test_re_register_keeps_history(self, reg):
        reg.register("x", _boom())
        reg.boot("x")
        assert reg.get("x").attempts == 1
        reg.register("x", lambda: None)           # hot-reload the callable
        assert reg.get("x").attempts == 1         # history survives
        assert reg.boot("x") is True

    def test_re_register_does_not_duplicate_order(self, reg):
        reg.register("x", lambda: None)
        reg.register("x", lambda: None)
        assert reg.names() == ["x"]


class TestConcurrency:
    def test_status_reads_are_safe_during_a_slow_install(self, reg):
        """The health server polls from its own thread while boot runs. The
        install must not hold the lock, or that read would block."""
        started = threading.Event()
        release = threading.Event()
        read_ok = threading.Event()

        def slow_install():
            started.set()
            release.wait(timeout=5)

        reg.register("slow", slow_install)
        t = threading.Thread(target=lambda: reg.boot("slow"), daemon=True)
        t.start()
        assert started.wait(timeout=5)
        # Mid-install: a snapshot from another thread must return promptly.
        reader = threading.Thread(
            target=lambda: (reg.snapshot(), read_ok.set()), daemon=True)
        reader.start()
        assert read_ok.wait(timeout=2), "snapshot blocked behind an install"
        release.set()
        t.join(timeout=5)
        assert reg.get("slow").state is SubsystemState.OK


class TestProcessWideDefault:
    def test_get_registry_is_a_singleton(self):
        reset_registry()
        try:
            assert get_registry() is get_registry()
        finally:
            reset_registry()

    def test_reset_registry_drops_it(self):
        reset_registry()
        a = get_registry()
        a.register("x", lambda: None)
        reset_registry()
        assert get_registry().names() == []
        reset_registry()
