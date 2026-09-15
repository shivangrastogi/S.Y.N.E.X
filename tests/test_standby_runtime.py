"""Tests for the standby runtime adapter (BrainLifecycle + StandbyController).

Uses a fake Brain ServiceProxy so the full wake→spin-up→answer→idle→spin-down
flow is verified with no real process spawn, model load, or threads.
"""

import pytest

from core.standby_runtime import BrainLifecycle, StandbyController
from core.standby_orchestrator import StandbyState
from core.standby_breaker import SpinUpBreaker, BreakerState
from core.standby_reflex import ReflexRouter


class _Msg:
    def __init__(self, payload):
        self.payload = payload


class _FakeProxy:
    """Mimics core.service_bus.ServiceProxy just enough for the adapter."""

    def __init__(self, start_ok=True, reply="hello ji", start_raises=False,
                 request_raises=None):
        self.started = False
        self.start_calls = 0
        self.stop_calls = 0
        self.requests = []
        self._start_ok = start_ok
        self._start_raises = start_raises
        self._reply = reply
        self._request_raises = request_raises  # an Exception class or None

    def start(self, ready_timeout=30.0):
        self.start_calls += 1
        if self._start_raises:
            raise RuntimeError("spawn boom")
        if self._start_ok:
            self.started = True
        return self._start_ok

    def is_alive(self):
        return self.started

    def stop(self, timeout=3.0):
        self.stop_calls += 1
        self.started = False

    def request(self, kind, payload=None, timeout=10.0):
        if self._request_raises is not None:
            raise self._request_raises("request boom")
        if not self.started:
            raise RuntimeError("not running")
        self.requests.append((kind, payload))
        return _Msg({"reply": self._reply, "skill": None})


class _Clock:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


# ── BrainLifecycle ───────────────────────────────────────────────────── #

def test_lifecycle_spin_up_ok():
    p = _FakeProxy()
    bl = BrainLifecycle(p)
    assert bl.spin_up() is True
    assert p.started is True


def test_lifecycle_spin_up_failure():
    assert BrainLifecycle(_FakeProxy(start_ok=False)).spin_up() is False


def test_lifecycle_spin_up_exception_is_safe():
    assert BrainLifecycle(_FakeProxy(start_raises=True)).spin_up() is False


def test_lifecycle_spin_down_only_when_alive():
    p = _FakeProxy()
    bl = BrainLifecycle(p)
    bl.spin_down()            # not started yet → no stop
    assert p.stop_calls == 0
    bl.spin_up()
    bl.spin_down()
    assert p.stop_calls == 1
    assert p.started is False


def test_lifecycle_ask_returns_reply():
    p = _FakeProxy(reply="42 hai")
    bl = BrainLifecycle(p)
    bl.spin_up()
    assert bl.ask("what is 6 times 7") == "42 hai"
    assert p.requests == [("utterance", {"text": "what is 6 times 7"})]


def test_lifecycle_ask_when_down_returns_none():
    # request raises RuntimeError when not running → None, not a crash.
    assert BrainLifecycle(_FakeProxy()).ask("hi") is None


def test_lifecycle_ask_timeout_returns_none():
    p = _FakeProxy(request_raises=TimeoutError)
    bl = BrainLifecycle(p)
    bl.spin_up()
    assert bl.ask("hi") is None


def test_lifecycle_ask_empty_reply_is_none():
    p = _FakeProxy(reply="")
    bl = BrainLifecycle(p)
    bl.spin_up()
    assert bl.ask("hi") is None


# ── StandbyController: the wake→answer→idle flow ─────────────────────── #

def _controller(proxy=None, idle_timeout_s=180, critical=15, clock=None, away=None,
                breaker=None, on_event=None, reflex=None, on_control=None):
    proxy = proxy or _FakeProxy()
    clock = clock or _Clock()
    ctl = StandbyController(
        brain=BrainLifecycle(proxy),
        idle_timeout_s=idle_timeout_s,
        away_idle_timeout_s=away,
        critical_battery_pct=critical,
        now=clock,
        breaker=breaker,
        on_event=on_event,
        reflex=reflex,
        on_control=on_control,
    )
    return ctl, proxy, clock


def test_controller_starts_dormant():
    ctl, proxy, _ = _controller()
    assert ctl.state is StandbyState.DORMANT
    assert proxy.start_calls == 0


def test_wake_spins_up_and_answers():
    ctl, proxy, _ = _controller(_FakeProxy(reply="namaste"))
    reply = ctl.handle_wake(lambda: "kaise ho")
    assert reply == "namaste"
    assert ctl.state is StandbyState.ACTIVE
    assert proxy.start_calls == 1
    assert proxy.requests == [("utterance", {"text": "kaise ho"})]


def test_wake_when_brain_wont_come_up():
    ctl, proxy, _ = _controller(_FakeProxy(start_ok=False))
    assert ctl.handle_wake(lambda: "hi") is None
    assert ctl.state is StandbyState.DORMANT
    assert proxy.requests == []  # never dispatched


def test_wake_with_no_speech_does_not_spin_up():
    # Transcribe-first: a false wake with no words must NOT pay a brain spawn.
    ctl, proxy, _ = _controller()
    assert ctl.handle_wake(lambda: None) is None
    assert ctl.state is StandbyState.DORMANT       # never woke the brain
    assert proxy.start_calls == 0                  # no spawn attempted
    assert proxy.requests == []                    # no dispatch


def test_wake_with_failing_stt_is_safe():
    def boom():
        raise RuntimeError("mic died")

    ctl, proxy, _ = _controller()
    assert ctl.handle_wake(boom) is None
    assert ctl.state is StandbyState.DORMANT       # STT failed → no spawn wasted
    assert proxy.start_calls == 0
    assert proxy.requests == []


def test_second_wake_does_not_respawn():
    ctl, proxy, _ = _controller()
    ctl.handle_wake(lambda: "one")
    ctl.handle_wake(lambda: "two")
    assert proxy.start_calls == 1
    assert len(proxy.requests) == 2


def test_idle_tick_spins_brain_down():
    ctl, proxy, clock = _controller(idle_timeout_s=120)
    ctl.handle_wake(lambda: "hi")
    assert ctl.state is StandbyState.ACTIVE
    clock.advance(120)
    ctl.tick()
    assert ctl.state is StandbyState.DORMANT
    assert proxy.stop_calls == 1


def test_wake_after_idle_teardown_respawns():
    ctl, proxy, clock = _controller(idle_timeout_s=60)
    ctl.handle_wake(lambda: "hi")
    clock.advance(60)
    ctl.tick()  # dormant
    ctl.handle_wake(lambda: "again")
    assert proxy.start_calls == 2
    assert ctl.state is StandbyState.ACTIVE


# ── presence-adaptive warm-time ─────────────────────────────────────── #

def test_on_user_idle_shortens_then_restores_timeout():
    ctl, _, _ = _controller(idle_timeout_s=180, away=30)
    ctl.on_user_idle(True)
    assert ctl._orch.idle_timeout_s == 30      # away → shorter
    ctl.on_user_idle(False)
    assert ctl._orch.idle_timeout_s == 180     # back → active


def test_on_user_idle_noop_without_away_configured():
    ctl, _, _ = _controller(idle_timeout_s=180, away=None)
    ctl.on_user_idle(True)
    assert ctl._orch.idle_timeout_s == 180     # unchanged — adaptation disabled


def test_away_timeout_spins_down_sooner_when_idle():
    ctl, proxy, clock = _controller(idle_timeout_s=180, away=30)
    ctl.handle_wake(lambda: "hi")              # ACTIVE, last activity now
    ctl.on_user_idle(True)                     # user stepped away → warm-time 30s
    clock.advance(35)                          # 35s > 30s away-timeout
    ctl.tick()
    assert ctl.state is StandbyState.DORMANT   # spun down on the short timeout
    assert proxy.stop_calls == 1


def test_active_conversation_survives_away_timeout():
    # The safety property: even after going "away", a live conversation (which
    # keeps refreshing activity) is never cut mid-turn.
    ctl, proxy, clock = _controller(idle_timeout_s=180, away=30)
    ctl.handle_wake(lambda: "hi")
    ctl.on_user_idle(True)                     # away-timeout 30s
    clock.advance(20)
    ctl.handle_wake(lambda: "follow-up")       # a real turn refreshes activity
    clock.advance(20)                          # 20s since that turn (< 30)
    ctl.tick()
    assert ctl.state is StandbyState.ACTIVE    # still warm — not cut off
    assert proxy.stop_calls == 0


# ── power reactions ─────────────────────────────────────────────────── #

def test_battery_critical_forces_dormant():
    ctl, proxy, _ = _controller(critical=15)
    ctl.handle_wake(lambda: "hi")
    ctl.on_power_change(on_battery=True, percent=10, plugged=False)
    assert ctl.state is StandbyState.DORMANT
    assert proxy.stop_calls == 1


def test_battery_ok_does_not_force_dormant():
    ctl, _, _ = _controller(critical=15)
    ctl.handle_wake(lambda: "hi")
    ctl.on_power_change(on_battery=True, percent=40, plugged=False)
    assert ctl.state is StandbyState.ACTIVE


def test_low_but_plugged_in_does_not_force_dormant():
    ctl, _, _ = _controller(critical=15)
    ctl.handle_wake(lambda: "hi")
    # Low percent but on AC power → keep the brain up.
    ctl.on_power_change(on_battery=False, percent=5, plugged=True)
    assert ctl.state is StandbyState.ACTIVE


# ── liveness self-healing (brain crashed while ACTIVE) ──────────────── #

def test_lifecycle_is_up_reflects_proxy():
    p = _FakeProxy()
    bl = BrainLifecycle(p)
    assert bl.is_up() is False        # not started yet
    bl.spin_up()
    assert bl.is_up() is True
    p.started = False                 # process died
    assert bl.is_up() is False


def test_tick_reconciles_a_dead_brain():
    ctl, proxy, clock = _controller(idle_timeout_s=180)
    ctl.handle_wake(lambda: "hi")
    assert ctl.state is StandbyState.ACTIVE
    proxy.started = False             # brain crashed (still "ACTIVE" in our view)
    ctl.tick()                        # a plain housekeeping tick catches it
    assert ctl.state is StandbyState.DORMANT
    assert ctl.crashes == 1


def test_healthy_brain_is_not_reconciled():
    ctl, _, clock = _controller(idle_timeout_s=180)
    ctl.handle_wake(lambda: "hi")
    clock.advance(10)                 # well under the idle timeout
    ctl.tick()
    assert ctl.state is StandbyState.ACTIVE   # alive → left alone
    assert ctl.crashes == 0


def test_dormant_brain_never_counts_as_a_crash():
    ctl, _, _ = _controller()
    assert ctl.state is StandbyState.DORMANT
    ctl.tick()                        # dormant is *expected* to be not-alive
    assert ctl.crashes == 0


def test_wake_after_crash_respawns_and_answers():
    ctl, proxy, _ = _controller()
    ctl.handle_wake(lambda: "hi")     # spin-up #1 → ACTIVE
    assert proxy.start_calls == 1
    proxy.started = False             # brain crashed mid-session
    reply = ctl.handle_wake(lambda: "you back?")  # next wake
    assert reply == "hello ji"        # answered, not swallowed by a dead brain
    assert proxy.start_calls == 2     # respawned a fresh brain
    assert ctl.state is StandbyState.ACTIVE
    assert ctl.crashes == 1


def test_crashes_counter_accumulates():
    ctl, proxy, _ = _controller()
    for _ in range(3):
        ctl.handle_wake(lambda: "hi")
        proxy.started = False         # crash again each round
    ctl.tick()                        # reconcile the final dead one
    assert ctl.crashes == 3


def test_brain_without_liveness_probe_is_assumed_alive():
    # A brain object lacking is_up() must never be reconciled (can't tell → alive).
    class _BrainNoProbe:
        def __init__(self):
            self.up = 0
        def spin_up(self):
            self.up += 1
            return True
        def spin_down(self):
            pass
        def ask(self, text):
            return "ok"
        # deliberately no is_up

    ctl = StandbyController(brain=_BrainNoProbe(), idle_timeout_s=180)
    ctl.handle_wake(lambda: "hi")
    ctl.tick()
    assert ctl.state is StandbyState.ACTIVE
    assert ctl.crashes == 0


# ── spin-up circuit breaker (brain won't start) ─────────────────────── #

def test_repeated_spinup_failures_trip_breaker_and_fail_fast():
    proxy = _FakeProxy(start_ok=False)          # brain refuses to come up
    clk = _Clock()
    brk = SpinUpBreaker(threshold=3, base_cooldown_s=10.0, now=clk)
    ctl, proxy, _ = _controller(proxy=proxy, clock=clk, breaker=brk)

    for _ in range(3):                          # three failed wakes → trip
        assert ctl.handle_wake(lambda: "hi") is None
    assert proxy.start_calls == 3
    assert ctl.breaker_state is BreakerState.OPEN

    # Breaker OPEN → the next wake must NOT attempt another spawn.
    assert ctl.handle_wake(lambda: "hi") is None
    assert proxy.start_calls == 3               # unchanged — failed fast


def test_breaker_recovers_after_cooldown():
    proxy = _FakeProxy(start_ok=False)
    clk = _Clock()
    brk = SpinUpBreaker(threshold=3, base_cooldown_s=10.0, now=clk)
    ctl, proxy, _ = _controller(proxy=proxy, clock=clk, breaker=brk)

    for _ in range(3):
        ctl.handle_wake(lambda: "hi")           # trip it
    assert ctl.breaker_state is BreakerState.OPEN

    clk.advance(10)                             # cooldown elapses → half-open
    proxy._start_ok = True                      # brain is healthy again now
    reply = ctl.handle_wake(lambda: "you back?")
    assert reply == "hello ji"                  # trial spin-up succeeded, answered
    assert ctl.state is StandbyState.ACTIVE
    assert ctl.breaker_state is BreakerState.CLOSED


def test_successful_wake_never_trips_breaker():
    ctl, _, _ = _controller()
    for _ in range(5):
        ctl.handle_wake(lambda: "hi")
        ctl.force_dormant()                     # spin down between wakes
    assert ctl.breaker_state is BreakerState.CLOSED


# ── journal events (crash / breaker) ─────────────────────────────────── #

def test_crash_emits_journal_event():
    events = []
    ctl, proxy, _ = _controller(on_event=lambda k, d: events.append((k, d)))
    ctl.handle_wake(lambda: "hi")
    proxy.started = False                       # brain crashed
    ctl.tick()                                  # reconcile → emit
    kinds = [k for k, _ in events]
    assert "crash" in kinds


def test_breaker_open_emits_journal_event():
    events = []
    clk = _Clock()
    brk = SpinUpBreaker(threshold=3, base_cooldown_s=10.0, now=clk)
    proxy = _FakeProxy(start_ok=False)
    ctl, proxy, _ = _controller(proxy=proxy, clock=clk, breaker=brk,
                                on_event=lambda k, d: events.append((k, d)))
    for _ in range(3):                          # 3 failures → trip
        ctl.handle_wake(lambda: "hi")
    assert "breaker_open" in [k for k, _ in events]


def test_breaker_close_emits_journal_event():
    events = []
    clk = _Clock()
    brk = SpinUpBreaker(threshold=3, base_cooldown_s=10.0, now=clk)
    proxy = _FakeProxy(start_ok=False)
    ctl, proxy, _ = _controller(proxy=proxy, clock=clk, breaker=brk,
                                on_event=lambda k, d: events.append((k, d)))
    for _ in range(3):
        ctl.handle_wake(lambda: "hi")           # trip open
    clk.advance(10)                             # cooldown → half-open
    proxy._start_ok = True                      # brain healthy now
    ctl.handle_wake(lambda: "back")             # trial succeeds → close
    assert "breaker_close" in [k for k, _ in events]


def test_no_event_callback_is_safe():
    # None on_event must never crash the crash/breaker paths.
    ctl, proxy, _ = _controller(on_event=None)
    ctl.handle_wake(lambda: "hi")
    proxy.started = False
    ctl.tick()                                  # crash path, no callback
    assert ctl.crashes == 1


# ── Tier-0 reflex fast-path (brain stays dormant) ────────────────────── #

class _Reflex:
    """Matches exactly one phrase → a canned reply."""
    def __init__(self, phrase="what time is it", reply="It's 3:45 PM."):
        self._phrase = phrase
        self._reply = reply
        self.calls = 0

    def match(self, text):
        self.calls += 1
        return self._reply if text == self._phrase else None


def test_reflex_answers_without_spinning_up_brain():
    ref = _Reflex()
    ctl, proxy, _ = _controller(reflex=ref)
    reply = ctl.handle_wake(lambda: "what time is it")
    assert reply == "It's 3:45 PM."
    assert ctl.state is StandbyState.DORMANT     # brain never woke
    assert proxy.start_calls == 0                # no spawn — the whole point


def test_reflex_miss_falls_through_to_brain():
    ref = _Reflex(phrase="what time is it")
    ctl, proxy, _ = _controller(reflex=ref)
    reply = ctl.handle_wake(lambda: "what's the capital of France")
    assert reply == "hello ji"                   # brain answered
    assert ctl.state is StandbyState.ACTIVE      # brain spun up for a real query
    assert proxy.start_calls == 1


def test_reflex_emits_journal_event():
    events = []
    ref = _Reflex()
    ctl, _, _ = _controller(reflex=ref, on_event=lambda k, d: events.append((k, d)))
    ctl.handle_wake(lambda: "what time is it")
    assert events and events[0][0] == "reflex"


def test_reflex_while_active_keeps_brain_warm():
    ref = _Reflex(phrase="what time is it")
    ctl, proxy, clock = _controller(reflex=ref, idle_timeout_s=180)
    ctl.handle_wake(lambda: "a real question")   # spins up → ACTIVE
    assert ctl.state is StandbyState.ACTIVE
    clock.advance(100)
    ctl.handle_wake(lambda: "what time is it")   # a reflex mid-session
    clock.advance(100)                           # 100s since the reflex (< 180)
    ctl.tick()
    assert ctl.state is StandbyState.ACTIVE       # reflex refreshed activity
    assert proxy.start_calls == 1                 # but never a second spawn


# ── Tier-0 control commands (voice power control) ────────────────────── #

def test_sleep_command_spins_brain_down():
    ctl, proxy, _ = _controller(reflex=ReflexRouter())
    ctl.handle_wake(lambda: "a real question")   # brain up → ACTIVE
    assert ctl.state is StandbyState.ACTIVE
    reply = ctl.handle_wake(lambda: "go to sleep")
    assert reply == "Going to sleep, sir."
    assert ctl.state is StandbyState.DORMANT      # dropped on command
    assert proxy.stop_calls == 1


def test_sleep_command_when_dormant_replies_without_spawn():
    ctl, proxy, _ = _controller(reflex=ReflexRouter())
    reply = ctl.handle_wake(lambda: "sona")
    assert reply == "Going to sleep, sir."
    assert ctl.state is StandbyState.DORMANT
    assert proxy.start_calls == 0                 # never woke the brain


def test_wake_command_spins_brain_up_without_dispatch():
    ctl, proxy, _ = _controller(reflex=ReflexRouter())
    reply = ctl.handle_wake(lambda: "wake up")
    assert reply == "I'm awake, sir."
    assert ctl.state is StandbyState.ACTIVE
    assert proxy.start_calls == 1
    assert proxy.requests == []                   # pre-warm only, no query asked


def test_wake_command_handles_spinup_failure_gracefully():
    proxy = _FakeProxy(start_ok=False)
    ctl, proxy, _ = _controller(proxy=proxy, reflex=ReflexRouter())
    reply = ctl.handle_wake(lambda: "wake up")
    assert reply == "I couldn't wake up just now, sir."
    assert ctl.state is StandbyState.DORMANT


def test_control_command_emits_journal_event():
    events = []
    ctl, _, _ = _controller(reflex=ReflexRouter(),
                            on_event=lambda k, d: events.append((k, d)))
    ctl.handle_wake(lambda: "go to sleep")
    assert ("control", "sleep") in events


def test_control_never_dispatches_to_brain():
    ctl, proxy, _ = _controller(reflex=ReflexRouter())
    ctl.handle_wake(lambda: "go to sleep")
    assert proxy.requests == []                   # control acts, never asks


# ── delegated (host/daemon-level) control actions ────────────────────── #

def test_unowned_control_is_delegated_to_host():
    seen = []
    def host(action):
        seen.append(action)
        return "Paused, sir."
    ctl, proxy, _ = _controller(reflex=ReflexRouter())
    ctl.set_on_control(host)
    reply = ctl.handle_wake(lambda: "pause listening")
    assert reply == "Paused, sir."
    assert seen == ["pause"]
    assert proxy.start_calls == 0                 # never woke the brain


def test_status_control_delegates_and_returns_host_reply():
    ctl, _, _ = _controller(reflex=ReflexRouter(),
                            on_control=lambda a: "I'm healthy, sir." if a == "status" else None)
    assert ctl.handle_wake(lambda: "system status") == "I'm healthy, sir."


def test_delegated_control_emits_journal_event():
    events = []
    ctl, _, _ = _controller(reflex=ReflexRouter(),
                            on_event=lambda k, d: events.append((k, d)),
                            on_control=lambda a: "ok")
    ctl.handle_wake(lambda: "pause")
    assert ("control", "pause") in events


def test_unowned_control_without_host_falls_through_to_brain():
    # "pause" is a control the controller doesn't own; with no host hook wired it
    # isn't handled in Tier-0 and falls through to the brain (safe degradation).
    ctl, proxy, _ = _controller(reflex=ReflexRouter())   # no on_control
    reply = ctl.handle_wake(lambda: "pause listening")
    assert reply == "hello ji"                    # brain answered
    assert proxy.start_calls == 1


def test_host_control_exception_is_swallowed():
    def boom(action):
        raise RuntimeError("daemon hiccup")
    ctl, proxy, _ = _controller(reflex=ReflexRouter(), on_control=boom)
    # Exception in the host hook → treated as "not handled" → no crash.
    reply = ctl.handle_wake(lambda: "pause")
    assert reply == "hello ji"                    # fell through to the brain
