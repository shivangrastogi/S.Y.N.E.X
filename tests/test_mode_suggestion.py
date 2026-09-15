"""Proactive Mode-suggestion source — deterministic clock + fake engine."""

from __future__ import annotations

import datetime as dt

from core.mode_suggestion import make_source


class _FakeEngine:
    def __init__(self, modes, active=()):
        self._modes = {m: {} for m in modes}
        self._active = set(active)

    def list_modes(self):
        return self._modes

    def active(self):
        return sorted(self._active)


def _at(y, mo, d, h):
    """epoch for a given local date/hour."""
    return dt.datetime(y, mo, d, h, 0, 0).timestamp()


def _src(modes, hour, active=(), weekday_date=(2026, 7, 22)):
    # 2026-07-22 is a Wednesday
    eng = _FakeEngine(modes, active)
    y, mo, d = weekday_date
    return make_source(now_fn=lambda: _at(y, mo, d, hour),
                       engine_getter=lambda: eng)()


class TestSleepSuggestion:
    def test_offers_sleep_in_window(self):
        out = _src(["sleep"], hour=22)
        assert len(out) == 1 and out[0].source_id == "mode_suggest:sleep"
        assert out[0].requested_level == 2          # an OFFER, never autonomous
        assert out[0].kind == "mode_suggest"

    def test_silent_outside_window(self):
        assert _src(["sleep"], hour=15) == []       # afternoon: nothing
        assert _src(["sleep"], hour=2) == []        # deep night: engine drops anyway

    def test_not_suggested_when_already_active(self):
        assert _src(["sleep"], hour=22, active=["sleep"]) == []

    def test_not_suggested_when_mode_absent(self):
        assert _src(["work"], hour=22) == []        # no sleep mode defined


class TestWorkSuggestion:
    def test_offers_work_weekday_morning(self):
        out = _src(["work"], hour=9, weekday_date=(2026, 7, 22))  # Wed
        assert len(out) == 1 and out[0].source_id == "mode_suggest:work"

    def test_not_on_weekend(self):
        assert _src(["work"], hour=9, weekday_date=(2026, 7, 25)) == []  # Sat


class TestSafety:
    def test_engine_failure_is_swallowed(self):
        def boom():
            raise RuntimeError("nope")
        out = make_source(now_fn=lambda: _at(2026, 7, 22, 22),
                          engine_getter=boom)()
        assert out == []

    def test_wires_into_live_engine(self):
        # the live engine must accept the source without error
        from core.initiative_engine import get_engine
        eng = get_engine()
        eng.candidates()   # should not raise
