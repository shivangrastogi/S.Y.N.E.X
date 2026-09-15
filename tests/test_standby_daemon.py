"""Tests for the headless StandbyDaemon (the Tier-0 driver).

Fakes for the controller, wake detector, power monitor, STT and TTS, plus an
injected ``sleep`` that ends the tick loop after N calls — so the loop body,
the wake callback and the start/stop wiring are all checked deterministically,
with no Vosk model, no mic, no process spawn and no real timing.
"""

import pytest

from core.standby_daemon import StandbyDaemon


class _FakeController:
    def __init__(self, reply="ok"):
        self.tick_calls = 0
        self.power_calls = []
        self.idle_calls = []
        self.stt_seen = "unset"
        self._reply = reply

    def handle_wake(self, stt):
        self.stt_seen = stt()  # exercise the STT wiring
        return self._reply

    def tick(self):
        self.tick_calls += 1

    def on_power_change(self, on_battery, percent, plugged):
        self.power_calls.append((on_battery, percent, plugged))

    def on_user_idle(self, is_idle):
        self.idle_calls.append(is_idle)


class _FakeWake:
    def __init__(self):
        self.cb = None
        self.stopped = 0

    def listen_async(self, on_wake):
        self.cb = on_wake

    def stop(self):
        self.stopped += 1

    def fire(self):
        return self.cb()


class _FakePower:
    def __init__(self):
        self.cb = None
        self.idle_cb = None

    def on_power_change(self, cb):
        self.cb = cb

    def on_idle_change(self, cb):
        self.idle_cb = cb

    def fire(self, on_battery, percent, plugged):
        self.cb(on_battery, percent, plugged)

    def fire_idle(self, idle_s, is_idle):
        self.idle_cb(idle_s, is_idle)


class _PowerNoIdle:
    """A power monitor that predates the idle signal (no on_idle_change)."""

    def __init__(self):
        self.cb = None

    def on_power_change(self, cb):
        self.cb = cb


def _daemon(*, controller=None, wake=None, power=None, stt=None, tts=None,
            stop_after_sleeps=1, checkpoint=None, checkpoint_interval_s=300.0):
    controller = controller or _FakeController()
    wake = wake or _FakeWake()
    box = {}

    def sleeper(_dt):
        box["n"] = box.get("n", 0) + 1
        if box["n"] >= stop_after_sleeps:
            box["d"]._stop.set()

    d = StandbyDaemon(
        controller=controller,
        wake_detector=wake,
        power_monitor=power,
        stt=stt or (lambda: "hi"),
        tts=tts,
        sleep=sleeper,
        checkpoint=checkpoint,
        checkpoint_interval_s=checkpoint_interval_s,
    )
    box["d"] = d
    return d, controller, wake


# ── wake callback ────────────────────────────────────────────────────── #

def test_on_wake_speaks_a_reply():
    spoken = []
    d, _, _ = _daemon(controller=_FakeController("hello ji"), tts=spoken.append)
    assert d.on_wake() == "hello ji"
    assert spoken == ["hello ji"]


def test_on_wake_no_reply_does_not_speak():
    spoken = []
    d, _, _ = _daemon(controller=_FakeController(reply=None), tts=spoken.append)
    assert d.on_wake() is None
    assert spoken == []


def test_on_wake_tts_exception_is_swallowed():
    def boom(_):
        raise RuntimeError("speaker died")

    d, _, _ = _daemon(controller=_FakeController("hi"), tts=boom)
    assert d.on_wake() == "hi"  # no raise


def test_on_wake_no_tts_configured_is_fine():
    d, _, _ = _daemon(controller=_FakeController("hi"), tts=None)
    assert d.on_wake() == "hi"


def test_on_wake_passes_stt_to_controller():
    d, ctl, _ = _daemon(controller=_FakeController("x"), stt=lambda: "kitne baje")
    d.on_wake()
    assert ctl.stt_seen == "kitne baje"


# ── tick loop ────────────────────────────────────────────────────────── #

def test_tick_loop_runs_until_stopped():
    d, ctl, _ = _daemon(stop_after_sleeps=3)
    d._run_ticks()  # synchronous; sleeper stops it after 3 iterations
    assert ctl.tick_calls == 3


def test_tick_loop_survives_a_tick_exception():
    class _Boom(_FakeController):
        def tick(self):
            self.tick_calls += 1
            raise RuntimeError("tick blew up")

    d, ctl, _ = _daemon(controller=_Boom(), stop_after_sleeps=2)
    d._run_ticks()  # must not propagate
    assert ctl.tick_calls == 2


# ── start / stop wiring ──────────────────────────────────────────────── #

def test_start_wires_wake_and_power_then_stop_cleans_up():
    power = _FakePower()
    d, ctl, wake = _daemon(power=power, stop_after_sleeps=1)
    d.start()
    assert wake.cb == d.on_wake            # wake → daemon.on_wake
    assert power.cb == d._on_power  # power → controller
    d.stop()
    assert wake.stopped == 1
    assert d.running is False


def test_firing_wake_after_start_runs_a_turn():
    spoken = []
    d, ctl, wake = _daemon(controller=_FakeController("namaste"), tts=spoken.append)
    d.start()
    wake.fire()  # the detector heard the wake word
    assert spoken == ["namaste"]
    d.stop()


def test_firing_power_after_start_reaches_controller():
    power = _FakePower()
    d, ctl, _ = _daemon(power=power)
    d.start()
    power.fire(True, 8, False)
    assert ctl.power_calls == [(True, 8, False)]
    d.stop()


def test_start_without_power_monitor_is_ok():
    d, _, wake = _daemon(power=None)
    d.start()          # no crash despite no power monitor
    assert wake.cb == d.on_wake
    d.stop()


# ── presence (idle) wiring ───────────────────────────────────────────── #

def test_start_subscribes_idle_when_supported():
    power = _FakePower()
    d, _, _ = _daemon(power=power)
    d.start()
    assert power.idle_cb == d._on_idle
    d.stop()


def test_firing_idle_reaches_controller():
    power = _FakePower()
    d, ctl, _ = _daemon(power=power)
    d.start()
    power.fire_idle(300, True)     # user went idle
    power.fire_idle(2, False)      # user came back
    assert ctl.idle_calls == [True, False]
    d.stop()


def test_idle_wiring_skipped_when_monitor_lacks_signal():
    # Old-style power monitor without on_idle_change must not break start().
    power = _PowerNoIdle()
    d, _, wake = _daemon(power=power)
    d.start()
    assert wake.cb == d.on_wake
    d.stop()


def test_on_idle_noop_if_controller_has_no_handler():
    class _Bare:
        def tick(self): pass
        def handle_wake(self, stt): return None
        def on_power_change(self, *a): pass
        # deliberately no on_user_idle
    d, _, _ = _daemon(controller=_Bare())
    d._on_idle(300, True)          # must not raise despite missing handler


# ── periodic lifetime checkpoint ─────────────────────────────────────── #

def test_checkpoint_every_computed_from_interval():
    # tick 5s, checkpoint every 300s → every 60 ticks.
    d, _, _ = _daemon(checkpoint=lambda: None, checkpoint_interval_s=300.0)
    assert d._checkpoint_every == 60


def test_checkpoint_fires_on_cadence():
    hits = []
    # tick 5s default, interval 15s → every 3 ticks. 6 ticks → fires at 3 and 6.
    d, _, _ = _daemon(checkpoint=lambda: hits.append(1),
                      checkpoint_interval_s=15.0, stop_after_sleeps=6)
    d._run_ticks()
    assert len(hits) == 2


def test_checkpoint_not_fired_before_interval():
    hits = []
    d, _, _ = _daemon(checkpoint=lambda: hits.append(1),
                      checkpoint_interval_s=15.0, stop_after_sleeps=2)
    d._run_ticks()
    assert hits == []          # only 2 ticks, first checkpoint is at tick 3


def test_checkpoint_exception_does_not_crash_loop():
    def boom():
        raise RuntimeError("disk full")
    # interval 5s == tick → every tick.
    d, ctl, _ = _daemon(checkpoint=boom, checkpoint_interval_s=5.0,
                        stop_after_sleeps=3)
    d._run_ticks()             # must not propagate
    assert ctl.tick_calls == 3


def test_no_checkpoint_configured_runs_clean():
    d, ctl, _ = _daemon(checkpoint=None, stop_after_sleeps=3)
    d._run_ticks()
    assert ctl.tick_calls == 3


# ── wake observer (feeds the raw wake count) ─────────────────────────── #

def test_wake_observer_called_on_wake():
    seen = []
    d, _, _ = _daemon()
    d._wake_observer = lambda: seen.append(1)
    d.on_wake()
    assert seen == [1]


def test_wake_observer_not_called_while_paused():
    seen = []
    d, _, _ = _daemon()
    d._wake_observer = lambda: seen.append(1)
    d.pause_listening()
    assert d.on_wake() is None
    assert seen == []              # paused wake is not counted


def test_wake_observer_exception_does_not_break_turn():
    def boom():
        raise RuntimeError("counter died")
    d, _, _ = _daemon(controller=_FakeController("hi"))
    d._wake_observer = boom
    assert d.on_wake() == "hi"     # turn still runs despite observer error


def test_no_wake_observer_is_fine():
    d, _, _ = _daemon(controller=_FakeController("hi"))
    assert d.on_wake() == "hi"


# ── degraded-state spoken feedback ───────────────────────────────────── #

def test_degraded_message_spoken_when_no_reply():
    spoken = []
    d, _, _ = _daemon(controller=_FakeController(reply=None), tts=spoken.append)
    d._degraded_check = lambda: "Brain unavailable, sir."
    assert d.on_wake() is None            # still no real reply
    assert spoken == ["Brain unavailable, sir."]


def test_degraded_check_not_consulted_when_reply_present():
    spoken, called = [], []
    d, _, _ = _daemon(controller=_FakeController("namaste"), tts=spoken.append)
    d._degraded_check = lambda: called.append(1) or "unused"
    assert d.on_wake() == "namaste"
    assert spoken == ["namaste"]          # the real reply, not the degraded msg
    assert called == []                   # never asked — we had a reply


def test_degraded_check_returning_none_stays_silent():
    spoken = []
    d, _, _ = _daemon(controller=_FakeController(reply=None), tts=spoken.append)
    d._degraded_check = lambda: None      # healthy → nothing to say
    assert d.on_wake() is None
    assert spoken == []


def test_degraded_check_exception_is_swallowed():
    spoken = []
    def boom():
        raise RuntimeError("health probe died")
    d, _, _ = _daemon(controller=_FakeController(reply=None), tts=spoken.append)
    d._degraded_check = boom
    assert d.on_wake() is None            # no crash
    assert spoken == []
