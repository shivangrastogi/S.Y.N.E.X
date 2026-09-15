"""Tests for routine graduation (core.routine_graduation) — Blueprint loop 3.
Injected clock + tmp path, no disk beyond tmp_path.
"""

from core.routine_graduation import GraduationTracker


def _t(tmp_path, threshold=3, now=1000.0):
    return GraduationTracker(str(tmp_path / "grad.json"),
                             threshold=threshold, now_fn=lambda: now)


# ── graduation on repeated accepts ─────────────────────────────────

def test_graduates_after_threshold_accepts(tmp_path):
    g = _t(tmp_path, threshold=3)
    assert g.record_accept("morning_dnd") is False   # 1
    assert g.record_accept("morning_dnd") is False   # 2
    assert g.record_accept("morning_dnd") is True    # 3 → graduates
    assert g.is_graduated("morning_dnd")
    assert "morning_dnd" in g.graduated_routines()


def test_further_accepts_dont_re_report_graduation(tmp_path):
    g = _t(tmp_path, threshold=2)
    g.record_accept("r")
    assert g.record_accept("r") is True              # graduates
    assert g.record_accept("r") is False             # already graduated


# ── revert un-graduates and blocks re-graduation ───────────────────

def test_revert_ungraduates_and_blocks(tmp_path):
    g = _t(tmp_path, threshold=2)
    g.record_accept("r")
    g.record_accept("r")            # graduated
    assert g.is_graduated("r")
    g.record_revert("r")
    assert not g.is_graduated("r")
    # further accepts must NOT re-graduate a reverted routine
    assert g.record_accept("r") is False
    assert not g.is_graduated("r")


# ── rejects never graduate ─────────────────────────────────────────

def test_rejects_alone_never_graduate(tmp_path):
    g = _t(tmp_path, threshold=2)
    g.record_reject("r")
    g.record_reject("r")
    assert not g.is_graduated("r")


# ── persistence ────────────────────────────────────────────────────

def test_survives_reload(tmp_path):
    path = str(tmp_path / "g.json")
    g1 = GraduationTracker(path, threshold=2, now_fn=lambda: 1000.0)
    g1.record_accept("r")
    g1.record_accept("r")           # graduates
    g2 = GraduationTracker(path, threshold=2, now_fn=lambda: 2000.0)
    assert g2.is_graduated("r")     # reloaded from disk


def test_status_tracks_counts(tmp_path):
    g = _t(tmp_path, threshold=5)
    g.record_accept("r")
    g.record_reject("r")
    s = g.status("r")
    assert s.accepts == 1 and s.rejects == 1 and not s.graduated
