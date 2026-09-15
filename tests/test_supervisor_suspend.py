"""Supervisor suspend/resume — the guard that lets the idle-brain hibernator
(§4.2, §6.22) stop the brain child WITHOUT the monitor treating it as a crash.

Lives apart from `test_service_supervisor.py` on purpose: that module is
slow-tagged wholesale because some of its tests spawn real child processes,
while these use a fake proxy and spawn nothing. This policy is what keeps
hibernation from quietly spending the crash-loop budget and disabling the very
crash-isolation §6.18/§6.19 exist to provide — it belongs in the fast lane.
"""

from __future__ import annotations

from core.service_bus import echo_handler_factory
from core.service_supervisor import READY, SUSPENDED, Supervisor

class _StoppableProxy:
    """Just the lifecycle surface `_check_once` and `health` touch — no spawn,
    so the suspend/resume policy stays in the fast lane."""

    def __init__(self):
        self.name = "brain"
        self.alive = True
        self.starts = 0

    def is_alive(self):
        return self.alive

    def is_ready(self):
        return self.alive

    def start(self, ready_timeout=0):
        self.starts += 1
        self.alive = True
        return True

    def stop(self, timeout=0):
        self.alive = False


class TestSuspend:
    """A deliberately retired child (idle-brain hibernation, §4.2) must not
    look like a crash to the monitor."""

    def _sup_with_fake(self):
        s = Supervisor(poll_interval=0.1, max_restarts=3, restart_window_s=60)
        s.register("brain", echo_handler_factory)
        p = _StoppableProxy()
        s._svcs["brain"].proxy = p
        return s, p

    def test_suspended_service_is_not_restarted(self):
        s, p = self._sup_with_fake()
        assert s.suspend("brain") is True
        p.stop()
        s._check_once(ready_timeout=1)
        assert p.starts == 0 and s.health()["brain"] == SUSPENDED

    def test_suspending_does_not_spend_the_crash_budget(self):
        """Otherwise a few sleep/wake cycles would mark the brain FAILED."""
        s, p = self._sup_with_fake()
        for _ in range(10):
            s.suspend("brain")
            p.stop()
            s._check_once(ready_timeout=1)
            s.resume("brain")
            p.start()
        assert s._svcs["brain"].restarts == []
        assert s._svcs["brain"].failed is False
        assert s.health()["brain"] == READY

    def test_resume_hands_supervision_back(self):
        s, p = self._sup_with_fake()
        s.suspend("brain")
        s.resume("brain")
        p.stop()
        s._check_once(ready_timeout=1)
        assert p.starts == 1 and s.health()["brain"] == READY

    def test_repeat_calls_and_unknown_names_are_no_ops(self):
        s, _ = self._sup_with_fake()
        assert s.suspend("brain") is True and s.suspend("brain") is False
        assert s.is_suspended("brain") is True
        assert s.resume("brain") is True and s.resume("brain") is False
        assert s.suspend("ghost") is False and s.resume("ghost") is False
        assert s.is_suspended("ghost") is False
