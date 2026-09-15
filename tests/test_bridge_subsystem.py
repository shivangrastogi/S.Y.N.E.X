"""The phone bridge as a supervised subsystem.

No network, no firebase-admin: `core.bridge_subsystem` reaches the bridge
through a lazy `_bridge()` indirection, so every test here swaps in a fake.

The classification tests deliberately assert against the *literal strings*
`CloudBridge.start()` returns, read out of the source. Matching on reason
substrings is brittle; the point of pinning them is that rewording one breaks
a test instead of silently dropping the bridge into the wrong bucket.
"""

from __future__ import annotations

import pytest

from core import bridge_subsystem as bs
from core.subsystem_registry import (
    SubsystemRegistry,
    SubsystemState,
    SubsystemUnavailable,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _FakeBridge:
    """Stands in for CloudBridge: same lifecycle surface, no Firestore."""

    def __init__(self, result=(True, "listening")):
        self.result = result
        self.starts = 0
        self.stops = 0
        self._started = False
        self._watch = object()

    def start(self, process_fn=None):
        self.starts += 1
        ok, reason = self.result
        self._started = bool(ok)
        if ok:
            self._watch = object()
        return ok, reason

    def stop(self):
        self.stops += 1
        self._started = False
        self._watch = None


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def reg(clock: _Clock) -> SubsystemRegistry:
    return SubsystemRegistry(clock=clock)


@pytest.fixture
def fake(monkeypatch) -> _FakeBridge:
    b = _FakeBridge()
    monkeypatch.setattr(bs, "_bridge", lambda: b)
    return b


# ── the literal strings cloud_bridge.start() can return ───────────── #

_DISABLED = "bridge disabled (AERIS_DISABLE_BRIDGE)"
_NO_HOOK = "brain hook not wired yet (boot incomplete?)"
_NOT_PAIRED = ("Not paired yet — say 'phone pair karo' to "
               "generate the QR.")
_NO_KEY = ("Service-account key missing — download it from Firebase "
           "console → Project settings → Service accounts, save as "
           "secrets/firebase_bridge.json")
_NO_SDK = "firebase-admin not importable: No module named 'firebase_admin'"
_CONNECT_FAILED = ("connect failed — Firebase unreachable "
                   "(network down?)")


class TestClassification:
    @pytest.mark.parametrize("reason", [_DISABLED, _NOT_PAIRED, _NO_KEY,
                                        _NO_SDK])
    def test_absent_preconditions_are_unavailable(self, reason):
        assert bs.classify(reason) == "unavailable"

    @pytest.mark.parametrize("reason", [_NO_HOOK, _CONNECT_FAILED])
    def test_races_are_retryable(self, reason):
        assert bs.classify(reason) == "retry"

    def test_unknown_reason_fails_loudly(self):
        assert bs.classify("something nobody predicted") == "failed"

    def test_empty_reason_fails(self):
        assert bs.classify("") == "failed"
        assert bs.classify(None) == "failed"

    def test_classification_is_case_insensitive(self):
        assert bs.classify("NOT PAIRED YET") == "unavailable"

    def test_the_strings_still_exist_in_cloud_bridge(self):
        """Guard against a reword in cloud_bridge silently re-bucketing a
        failure. If this fails, update BOTH the source string and the
        marker table in bridge_subsystem."""
        import inspect
        from core import cloud_bridge
        src = inspect.getsource(cloud_bridge)
        for fragment in ("bridge disabled (AERIS_DISABLE_BRIDGE)",
                         "brain hook not wired yet",
                         "Not paired yet",
                         "Service-account key missing",
                         "firebase-admin not importable",
                         "connect failed — Firebase unreachable"):
            assert fragment in src, f"cloud_bridge no longer says: {fragment}"

    def test_connect_failure_is_not_reported_as_ok(self):
        """Regression: start() used to return available()[1] when _connect()
        failed, so a network outage reported the reason "ok" — which
        classifies as an unknown failure and never retries."""
        assert bs.classify("ok") != "retry"      # "ok" is not a real reason
        assert bs.classify(_CONNECT_FAILED) == "retry"


class TestInstall:
    def test_success_leaves_it_ok(self, reg, fake):
        bs.register(reg)
        assert reg.boot(bs.NAME) is True
        assert reg.get(bs.NAME).state is SubsystemState.OK
        assert fake.starts == 1

    def test_absent_precondition_disables_without_shouting(self, reg, fake):
        fake.result = (False, _NOT_PAIRED)
        bs.register(reg)
        assert reg.boot(bs.NAME) is False
        rec = reg.get(bs.NAME)
        assert rec.state is SubsystemState.DISABLED
        assert "Not paired" in rec.last_error
        # DISABLED is not a fault: the roll-up stays healthy.
        assert reg.snapshot()["ok"] is True
        assert reg.snapshot()["failed"] == []

    def test_disabled_bridge_does_not_burn_retry_budget(self, reg, fake,
                                                        clock):
        fake.result = (False, _DISABLED)
        bs.register(reg)
        reg.boot(bs.NAME)
        clock.advance(10_000)
        assert reg.due_for_retry() == []
        assert fake.starts == 1              # never tried again

    def test_race_is_retried(self, reg, fake, clock):
        fake.result = (False, _NO_HOOK)
        bs.register(reg)
        assert reg.boot(bs.NAME) is False
        assert reg.get(bs.NAME).state is SubsystemState.RETRYING
        clock.advance(bs._BACKOFF_S + 1)
        assert reg.due_for_retry() == [bs.NAME]

    def test_the_boot_race_actually_resolves(self, reg, fake, clock):
        """The real sequence: bridge starts before the brain hook is wired,
        then the brain comes up and the reconnect succeeds."""
        fake.result = (False, _NO_HOOK)
        bs.register(reg)
        reg.boot(bs.NAME)
        fake.result = (True, "listening")    # brain finished booting
        clock.advance(bs._BACKOFF_S + 1)
        assert reg.retry_due() == {bs.NAME: True}
        assert reg.get(bs.NAME).state is SubsystemState.OK

    def test_unknown_failure_exhausts_budget_then_stops(self, reg, fake,
                                                        clock):
        fake.result = (False, "kaboom")
        bs.register(reg)
        reg.boot(bs.NAME)
        for _ in range(6):
            clock.advance(10_000)
            reg.retry_due()
        assert reg.get(bs.NAME).state is SubsystemState.FAILED
        assert fake.starts == 1 + bs._MAX_RETRIES

    def test_installer_raises_the_right_exception_types(self, fake):
        fake.result = (False, _NOT_PAIRED)
        with pytest.raises(SubsystemUnavailable):
            bs.make_installer()()
        fake.result = (False, _NO_HOOK)
        with pytest.raises(RuntimeError):
            bs.make_installer()()

    def test_process_fn_is_forwarded(self, reg, monkeypatch):
        seen = []

        class _B(_FakeBridge):
            def start(self, process_fn=None):
                seen.append(process_fn)
                return True, "listening"

        monkeypatch.setattr(bs, "_bridge", lambda: _B())
        fn = lambda t: t                                   # noqa: E731
        bs.register(reg, process_fn=fn)
        reg.boot(bs.NAME)
        assert seen == [fn]


class TestReconnect:
    def test_reconnect_stops_before_starting(self, reg, fake):
        """start() is idempotent and returns "already running" while
        _started is True — a reconnect that skipped stop() would be a no-op
        reporting success."""
        bs.register(reg)
        reg.boot(bs.NAME)
        assert fake._started is True
        reg.reconnect(bs.NAME)
        assert fake.stops == 1
        assert fake.starts == 2

    def test_rearm_revives_a_disabled_bridge(self, reg, fake):
        fake.result = (False, _NOT_PAIRED)
        bs.register(reg)
        reg.boot(bs.NAME)
        assert reg.get(bs.NAME).state is SubsystemState.DISABLED
        fake.result = (True, "listening")        # user just paired
        assert bs.rearm(reg) is True
        assert reg.get(bs.NAME).state is SubsystemState.OK

    def test_rearm_registers_when_not_registered_yet(self, reg, fake):
        assert reg.get(bs.NAME) is None
        assert bs.rearm(reg) is True
        assert reg.get(bs.NAME).state is SubsystemState.OK

    def test_rearm_clears_a_failed_verdict(self, reg, fake, clock):
        fake.result = (False, "kaboom")
        bs.register(reg)
        reg.boot(bs.NAME)
        for _ in range(6):
            clock.advance(10_000)
            reg.retry_due()
        assert reg.get(bs.NAME).state is SubsystemState.FAILED
        fake.result = (True, "listening")
        assert bs.rearm(reg) is True
        assert reg.get(bs.NAME).retries_left == bs._MAX_RETRIES


class TestLiveness:
    def test_healthy_bridge_passes(self, reg, fake):
        bs.register(reg)
        reg.boot(bs.NAME)
        assert bs.check_liveness(reg) is True
        assert reg.get(bs.NAME).state is SubsystemState.OK

    def test_silent_listener_death_is_caught(self, reg, fake, clock):
        """The bug this exists for: the Firestore listener dies, `_started`
        stays True, and the bridge looks healthy while receiving nothing."""
        bs.register(reg)
        reg.boot(bs.NAME)
        fake._watch = None                       # listener died quietly
        assert bs.check_liveness(reg) is False
        assert reg.get(bs.NAME).state is SubsystemState.DEGRADED
        clock.advance(bs._BACKOFF_S + 1)
        assert reg.due_for_retry() == [bs.NAME]  # reconnect scheduled

    def test_closed_watch_is_caught(self, reg, fake):
        class _ClosedWatch:
            _closed = True

        bs.register(reg)
        reg.boot(bs.NAME)
        fake._watch = _ClosedWatch()
        assert bs.check_liveness(reg) is False
        assert reg.get(bs.NAME).state is SubsystemState.DEGRADED

    def test_watch_without_a_closed_attribute_is_given_the_benefit(
            self, reg, fake):
        """firebase-admin versions differ; absence of the attribute must
        read as "no opinion", not "dead" — a false reconnect every 5 s would
        be worse than a missed one."""
        fake._watch = object()                   # no _closed, no closed
        bs.register(reg)
        reg.boot(bs.NAME)
        assert bs.check_liveness(reg) is True

    def test_stopped_outside_the_supervisor_is_caught(self, reg, fake):
        bs.register(reg)
        reg.boot(bs.NAME)
        fake._started = False                    # a skill called stop()
        assert bs.check_liveness(reg) is False
        assert reg.get(bs.NAME).state is SubsystemState.DEGRADED

    def test_liveness_on_a_down_bridge_is_a_no_op(self, reg, fake):
        fake.result = (False, _NOT_PAIRED)
        bs.register(reg)
        reg.boot(bs.NAME)
        assert bs.check_liveness(reg) is False
        # still DISABLED — the probe must not promote it to DEGRADED
        assert reg.get(bs.NAME).state is SubsystemState.DISABLED

    def test_liveness_on_an_unregistered_bridge_is_a_no_op(self, reg):
        assert bs.check_liveness(reg) is False

    def test_probe_never_raises(self, reg, monkeypatch):
        class _Explosive:
            @property
            def _started(self):
                raise RuntimeError("boom")

        bs.register(reg)
        monkeypatch.setattr(bs, "_bridge", lambda: _FakeBridge())
        reg.boot(bs.NAME)
        monkeypatch.setattr(bs, "_bridge", lambda: _Explosive())
        assert bs.check_liveness(reg) is True     # assumed alive, not crashed


class TestUnavailableInRegistry:
    """`SubsystemUnavailable` semantics, exercised through the registry."""

    def test_it_disables_rather_than_failing(self):
        reg = SubsystemRegistry()

        def _install():
            raise SubsystemUnavailable("no camera on this machine")

        reg.register("vision", _install, max_retries=3)
        assert reg.boot("vision") is False
        rec = reg.get("vision")
        assert rec.state is SubsystemState.DISABLED
        assert "no camera" in rec.last_error

    def test_it_does_not_spend_retry_budget(self):
        clock = _Clock()
        reg = SubsystemRegistry(clock=clock)
        calls = []

        def _install():
            calls.append(1)
            raise SubsystemUnavailable("not set up")

        reg.register("x", _install, max_retries=2, backoff_s=1.0)
        reg.boot("x")
        clock.advance(10_000)
        assert reg.due_for_retry() == []
        # Budget intact for when the precondition is met.
        assert reg.get("x").retries_left == 2
        assert len(calls) == 1

    def test_it_is_excluded_from_critical_down(self):
        reg = SubsystemRegistry()

        def _install():
            raise SubsystemUnavailable("nope")

        reg.register("x", _install, critical=True)
        reg.boot("x")
        assert reg.snapshot()["critical_down"] == []
        assert reg.snapshot()["ok"] is True
