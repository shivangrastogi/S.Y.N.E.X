"""End-to-end integration of the whole standby stack via build_standby_stack.

Unlike the per-module unit tests, this composes the REAL controller, orchestrator,
breaker, reflex, stats, journal, health, power policy and quiet hours together
exactly as main.py does — through the shared factory — and drives full sessions.
It's the closest testable proxy for the on-device smoke: it catches WIRING bugs
(the composition), not just per-component logic. Only the IO edges are faked
(brain proxy, mic, wake detector); clocks are injected for determinism.
"""

from datetime import datetime

import pytest

from core.standby_app import build_standby_stack
from core.standby_runtime import BrainLifecycle
from core.standby_config import StandbyConfig
from core.standby_orchestrator import StandbyState


# ── fakes for the IO edges ───────────────────────────────────────────── #

class _Proxy:
    """A fake brain ServiceProxy (echoes a fixed reply)."""
    def __init__(self, reply="a joke about cats", start_ok=True):
        self.started = False
        self.start_calls = 0
        self.stop_calls = 0
        self.requests = []
        self._reply = reply
        self._start_ok = start_ok

    def start(self, ready_timeout=30.0):
        self.start_calls += 1
        if self._start_ok:
            self.started = True
        return self._start_ok

    def is_alive(self):
        return self.started

    def stop(self, timeout=3.0):
        self.stop_calls += 1
        self.started = False

    def request(self, kind, payload=None, timeout=10.0):
        if not self.started:
            raise RuntimeError("not running")
        self.requests.append((kind, payload))
        return type("M", (), {"payload": {"reply": self._reply}})()


class _Mic:
    def __init__(self):
        self.next = None

    def listen(self):
        return self.next


class _Wake:
    def listen_async(self, cb):
        self.cb = cb

    def pause(self):
        pass

    def resume(self):
        pass

    def stop(self):
        pass


class _Mono:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def adv(self, d):
        self.t += d


def _cfg(**over):
    base = {"standby.idle_timeout_s": 100}
    base.update(over)
    return StandbyConfig.from_settings(lambda k, d=None: base.get(k, d))


def _build(tmp_path, *, proxy=None, mic=None, mono=None,
           wall=datetime(2026, 8, 16, 15, 0), cfg=None):
    proxy = proxy or _Proxy()
    mic = mic or _Mic()
    mono = mono or _Mono()
    stack = build_standby_stack(
        brain=BrainLifecycle(proxy),
        stt=mic.listen,
        wake_detector=_Wake(),
        cfg=cfg or _cfg(),
        stats_path=str(tmp_path / "stats.json"),
        journal_path=str(tmp_path / "journal.json"),
        now=mono,
        now_dt=lambda: wall,
    )
    return stack, proxy, mic, mono


# ── scenarios ────────────────────────────────────────────────────────── #

def test_reflex_query_answered_without_waking_brain(tmp_path):
    stack, proxy, mic, _ = _build(tmp_path)
    mic.next = "what time is it"
    reply = stack.daemon.on_wake()
    assert reply == "It's 3:00 PM."            # reflex, wall clock 15:00
    assert proxy.start_calls == 0              # brain never spawned
    assert stack.controller.state is StandbyState.DORMANT
    assert stack.journal.count("reflex") == 1
    assert stack.stats.snapshot()["spinups"] == 0


def test_real_query_spins_up_and_answers(tmp_path):
    stack, proxy, mic, _ = _build(tmp_path)
    mic.next = "tell me a joke"
    reply = stack.daemon.on_wake()
    assert reply == "a joke about cats"
    assert proxy.start_calls == 1
    assert proxy.requests == [("utterance", {"text": "tell me a joke"})]
    assert stack.controller.state is StandbyState.ACTIVE
    assert stack.stats.snapshot()["spinups"] == 1


def test_full_lifecycle_wake_idle_crash_recover(tmp_path):
    stack, proxy, mic, mono = _build(tmp_path)

    # reflex (no spawn) → real query (spawn) → idle spin-down
    mic.next = "what time is it"; stack.daemon.on_wake()
    mic.next = "tell me a joke"; stack.daemon.on_wake()
    assert stack.controller.state is StandbyState.ACTIVE
    mono.adv(101)
    stack.controller.tick()
    assert stack.controller.state is StandbyState.DORMANT
    assert proxy.stop_calls == 1

    # respawn on the next real query, then crash it, then reconcile
    mic.next = "another joke"; stack.daemon.on_wake()
    assert stack.controller.state is StandbyState.ACTIVE
    assert proxy.start_calls == 2
    proxy.started = False                       # brain died
    stack.controller.tick()                     # liveness reconcile
    assert stack.controller.state is StandbyState.DORMANT
    assert stack.controller.crashes == 1

    # telemetry + journal reflect the whole session coherently
    snap = stack.stats.snapshot()
    assert snap["spinups"] == 2                  # two real spin-ups
    assert snap["wakes"] == 3                    # every on_wake counts
    summary = stack.journal.summary()
    assert summary.get("wake") == 3
    assert summary.get("reflex") == 1
    assert summary.get("spinup") == 2
    assert summary.get("crash") == 1
    assert "boot" in summary
    assert stack.health.healthy() is True        # self-healed → not degraded


def test_sleep_control_drops_brain(tmp_path):
    stack, proxy, mic, _ = _build(tmp_path)
    mic.next = "tell me a joke"; stack.daemon.on_wake()      # ACTIVE
    assert stack.controller.state is StandbyState.ACTIVE
    mic.next = "go to sleep"
    reply = stack.daemon.on_wake()
    assert reply == "Going to sleep, sir."
    assert stack.controller.state is StandbyState.DORMANT
    assert stack.journal.count("control") >= 1


def test_status_control_speaks_health(tmp_path):
    stack, _, mic, _ = _build(tmp_path)
    mic.next = "system status"
    reply = stack.daemon.on_wake()
    assert reply.startswith("I'm healthy")
    assert "the brain is" in reply


def test_lifetime_persists_across_rebuild(tmp_path):
    stack, proxy, mic, _ = _build(tmp_path)
    mic.next = "tell me a joke"; stack.daemon.on_wake()
    stack.store.commit(stack.stats.snapshot())              # bank the session
    stack.journal.flush()

    # a *fresh* stack over the same paths sees the prior session + journal.
    stack2, *_ = _build(tmp_path)
    assert stack2.lifetime.sessions == 1
    assert stack2.journal.count("wake") >= 1                # persisted events


def test_quiet_hours_wired_from_config(tmp_path):
    cfg = _cfg(**{"standby.quiet_start": "23:00", "standby.quiet_end": "07:00"})
    stack, *_ = _build(tmp_path, wall=datetime(2026, 8, 16, 2, 0), cfg=cfg)  # 2am
    assert stack.daemon.in_quiet_hours() is True


def test_health_report_renders_on_wired_stack(tmp_path):
    stack, _, mic, _ = _build(tmp_path)
    mic.next = "tell me a joke"; stack.daemon.on_wake()
    text = stack.health.format_report()
    assert "brain:" in text and "breaker:" in text and "session:" in text
    line = stack.controls.status_line()
    assert "AERIS" in line
