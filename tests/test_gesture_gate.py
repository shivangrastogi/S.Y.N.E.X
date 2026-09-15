"""Tests for core.gesture_gate — presence-gated gesture arming, with fakes."""
import core.gesture_gate as gg
import core.eternal_presence as ep


class _FakeEngine:
    """Stand-in for the gesture engine: just tracks enabled state."""
    def __init__(self, enabled=False):
        self._enabled = enabled
        self.starts = 0
        self.stops = 0

    def is_enabled(self):
        return self._enabled

    def start(self):
        self._enabled = True
        self.starts += 1
        return True

    def stop(self):
        self._enabled = False
        self.stops += 1


def _gate(enabled=True, privacy=False):
    eng = _FakeEngine(enabled=enabled)
    gate = gg.GestureGate(engine=eng, privacy=lambda: privacy)
    return gate, eng


def test_disarms_when_user_goes_away():
    gate, eng = _gate(enabled=True)
    gate.on_state("away", "active")
    assert eng._enabled is False
    assert eng.stops == 1


def test_idle_also_disarms():
    gate, eng = _gate(enabled=True)
    gate.on_state("idle", "active")
    assert eng._enabled is False


def test_rearms_only_what_gate_paused():
    gate, eng = _gate(enabled=True)
    gate.on_state("away", "active")          # gate pauses it
    assert eng._enabled is False
    gate.on_state("active", "away")          # gate should resume it
    assert eng._enabled is True
    assert eng.starts == 1


def test_does_not_force_start_user_disabled_engine():
    # engine was off and the gate never paused it → arriving must NOT start it
    gate, eng = _gate(enabled=False)
    gate.on_state("active", "away")
    assert eng._enabled is False
    assert eng.starts == 0


def test_privacy_keeps_it_disarmed():
    gate, eng = _gate(enabled=True, privacy=True)
    gate.on_state("active", "idle")          # would normally arm/stay
    assert eng._enabled is False             # privacy forces disarm


def test_state_listener_channel_fires():
    """The engine actually fans out transitions to state listeners."""
    e = ep.EternalPresence(heartbeat_s=1.0)
    seen = []
    e.add_state_listener(lambda new, prev: seen.append((prev, new)))
    e._cam_present = True
    e._fuse()                                 # AWAY -> ACTIVE transition
    assert seen and seen[-1][1] in ep._ALL_STATES
