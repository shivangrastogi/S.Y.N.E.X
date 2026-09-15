"""Tests for nightly memory consolidation (core.memory_consolidation).
Injected fabric + llm + clock + tmp marker — no model, no real memory.
Blueprint learning loop 2 / Year Q1·M1 nightly job.
"""

from datetime import datetime

from core.memory_consolidation import Consolidator, seconds_until_next


class FakeFabric:
    def __init__(self):
        self.calls = 0

    def consolidate(self, llm=None):
        self.calls += 1
        return llm("blob") if llm else None


def _con(tmp_path, llm=lambda p: "You coded all evening.", now=None):
    return Consolidator(
        fabric_provider=lambda: FakeFabric(),
        llm=llm,
        now_fn=(lambda: now) if now else __import__("time").time,
        marker_path=str(tmp_path / "consolidation.marker"),
    )


def _ts(y, m, d, h=4):
    return datetime(y, m, d, h, 0).timestamp()


# ── idempotency ───────────────────────────────────────────────────

def test_consolidates_once_then_skips_same_day(tmp_path):
    now = _ts(2026, 7, 12)
    c = _con(tmp_path, now=now)
    assert c.consolidate() == "You coded all evening."
    assert c.already_done_today()
    assert c.consolidate() is None          # same day → no-op


def test_runs_again_next_day(tmp_path):
    path = str(tmp_path / "m.marker")
    c1 = Consolidator(fabric_provider=lambda: FakeFabric(),
                      llm=lambda p: "day one",
                      now_fn=lambda: _ts(2026, 7, 12), marker_path=path)
    assert c1.consolidate() == "day one"
    c2 = Consolidator(fabric_provider=lambda: FakeFabric(),
                      llm=lambda p: "day two",
                      now_fn=lambda: _ts(2026, 7, 13), marker_path=path)
    assert c2.consolidate() == "day two"    # new day → runs


def test_force_ignores_marker(tmp_path):
    now = _ts(2026, 7, 12)
    c = _con(tmp_path, now=now)
    c.consolidate()
    assert c.consolidate(force=True) == "You coded all evening."


def test_no_llm_is_safe_noop(tmp_path):
    c = _con(tmp_path, llm=None, now=_ts(2026, 7, 12))
    assert c.consolidate() is None
    assert not c.already_done_today()       # nothing ran, nothing marked


def test_set_llm_wires_summarizer_after_construction(tmp_path):
    c = _con(tmp_path, llm=None, now=_ts(2026, 7, 12))
    assert c.consolidate() is None          # no summarizer yet
    c.set_llm(lambda p: "wired summary")
    assert c.consolidate() == "wired summary"


def test_empty_summary_still_marks_day(tmp_path):
    # an idle day (llm returns nothing) shouldn't retry every tick
    c = _con(tmp_path, llm=lambda p: "", now=_ts(2026, 7, 12))
    assert c.consolidate() == ""
    assert c.already_done_today()


def test_marker_survives_reload(tmp_path):
    path = str(tmp_path / "m.marker")
    now = _ts(2026, 7, 12)
    Consolidator(fabric_provider=lambda: FakeFabric(),
                 llm=lambda p: "x", now_fn=lambda: now,
                 marker_path=path).consolidate()
    fresh = Consolidator(fabric_provider=lambda: FakeFabric(),
                         llm=lambda p: "x", now_fn=lambda: now,
                         marker_path=path)
    assert fresh.already_done_today()       # marker read from disk


# ── scheduling helper ─────────────────────────────────────────────

def test_seconds_until_next_today_ahead():
    now = _ts(2026, 7, 12, 1)               # 01:00
    s = seconds_until_next(3, 17, now)      # 03:17 today
    assert 2 * 3600 < s < 2.5 * 3600


def test_seconds_until_next_rolls_to_tomorrow():
    now = _ts(2026, 7, 12, 5)               # 05:00, past 03:17
    s = seconds_until_next(3, 17, now)      # → tomorrow 03:17
    assert 22 * 3600 < s < 23 * 3600
