"""Tests for StandbyConfig — settings loading, clamping, and bad-value safety."""

import pytest

from core.standby_config import StandbyConfig


def _get(d):
    """A settings.get-shaped getter backed by a dict."""
    return lambda key, default=None: d.get(key, default)


def test_defaults_when_settings_empty():
    c = StandbyConfig.from_settings(_get({}))
    assert c.idle_timeout_s == 180.0
    assert c.critical_battery_pct == 15
    assert c.keep_awake_on_battery is True
    assert c.tick_interval_s == 5.0
    assert c.ask_timeout_s == 12.0


def test_reads_configured_values():
    c = StandbyConfig.from_settings(_get({
        "standby.idle_timeout_s": 300,
        "standby.critical_battery_pct": 20,
        "standby.keep_awake_on_battery": False,
        "standby.tick_interval_s": 10,
        "standby.ask_timeout_s": 30,
    }))
    assert c.idle_timeout_s == 300
    assert c.critical_battery_pct == 20
    assert c.keep_awake_on_battery is False
    assert c.tick_interval_s == 10
    assert c.ask_timeout_s == 30


def test_clamps_out_of_range_values():
    c = StandbyConfig.from_settings(_get({
        "standby.idle_timeout_s": 5,          # below min 10
        "standby.critical_battery_pct": 0,    # below min 1
        "standby.tick_interval_s": 0.1,       # below min 1
    }))
    assert c.idle_timeout_s == 10.0
    assert c.critical_battery_pct == 1
    assert c.tick_interval_s == 1.0

    c2 = StandbyConfig.from_settings(_get({
        "standby.idle_timeout_s": 99999,      # above max 3600
        "standby.critical_battery_pct": 200,  # above max 99
        "standby.ask_timeout_s": 999,         # above max 120
    }))
    assert c2.idle_timeout_s == 3600.0
    assert c2.critical_battery_pct == 99
    assert c2.ask_timeout_s == 120.0


def test_bad_type_falls_back_to_default():
    c = StandbyConfig.from_settings(_get({
        "standby.idle_timeout_s": "not a number",
        "standby.tick_interval_s": None,
    }))
    assert c.idle_timeout_s == 180.0
    assert c.tick_interval_s == 5.0


@pytest.mark.parametrize("raw,expected", [
    (False, False), (True, True),
    (0, False), (1, True),
    ("false", False), ("no", False), ("off", False), ("0", False),
    ("true", True), ("yes", True), ("on", True), ("1", True),
    ([], True),  # unknown type → default (True)
])
def test_flag_coercion(raw, expected):
    c = StandbyConfig.from_settings(_get({"standby.keep_awake_on_battery": raw}))
    assert c.keep_awake_on_battery is expected


def test_away_idle_timeout_default():
    c = StandbyConfig.from_settings(_get({}))
    assert c.away_idle_timeout_s == 30.0


def test_away_idle_timeout_configured():
    c = StandbyConfig.from_settings(_get({
        "standby.idle_timeout_s": 300,
        "standby.away_idle_timeout_s": 45,
    }))
    assert c.away_idle_timeout_s == 45.0


def test_away_idle_timeout_capped_at_active_timeout():
    # An away warm-time longer than the active one is nonsense → clamp to active.
    c = StandbyConfig.from_settings(_get({
        "standby.idle_timeout_s": 60,
        "standby.away_idle_timeout_s": 500,
    }))
    assert c.away_idle_timeout_s == 60.0


def test_away_idle_timeout_floored():
    c = StandbyConfig.from_settings(_get({
        "standby.away_idle_timeout_s": 1,     # below the 5s floor
    }))
    assert c.away_idle_timeout_s == 5.0


def test_checkpoint_interval_default():
    c = StandbyConfig.from_settings(_get({}))
    assert c.checkpoint_interval_s == 300.0


def test_checkpoint_interval_configured():
    c = StandbyConfig.from_settings(_get({"standby.checkpoint_interval_s": 120}))
    assert c.checkpoint_interval_s == 120.0


def test_checkpoint_interval_clamped():
    lo = StandbyConfig.from_settings(_get({"standby.checkpoint_interval_s": 1}))
    assert lo.checkpoint_interval_s == 30.0     # floor
    hi = StandbyConfig.from_settings(_get({"standby.checkpoint_interval_s": 999999}))
    assert hi.checkpoint_interval_s == 3600.0   # ceiling


def test_breaker_defaults():
    c = StandbyConfig.from_settings(_get({}))
    assert c.breaker_threshold == 3
    assert c.breaker_cooldown_s == 10.0


def test_breaker_configured_and_clamped():
    c = StandbyConfig.from_settings(_get({
        "standby.breaker_threshold": 5,
        "standby.breaker_cooldown_s": 60,
    }))
    assert c.breaker_threshold == 5
    assert c.breaker_cooldown_s == 60.0

    clamped = StandbyConfig.from_settings(_get({
        "standby.breaker_threshold": 0,       # below min 1
        "standby.breaker_cooldown_s": 9999,   # above max 600
    }))
    assert clamped.breaker_threshold == 1
    assert clamped.breaker_cooldown_s == 600.0


def test_quiet_hours_default_empty():
    c = StandbyConfig.from_settings(_get({}))
    assert c.quiet_start == ""
    assert c.quiet_end == ""


def test_quiet_hours_read():
    c = StandbyConfig.from_settings(_get({
        "standby.quiet_start": "23:00",
        "standby.quiet_end": "07:00",
    }))
    assert c.quiet_start == "23:00"
    assert c.quiet_end == "07:00"


def test_quiet_hours_none_coerced_to_empty():
    c = StandbyConfig.from_settings(_get({"standby.quiet_start": None}))
    assert c.quiet_start == ""


def test_summary_is_human():
    c = StandbyConfig()
    assert "idle" in c.summary()
    assert "battery" in c.summary()
    assert "away" in c.summary()
