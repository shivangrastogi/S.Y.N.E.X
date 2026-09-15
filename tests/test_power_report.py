"""Tests for the standby power-report harness.

The footprint / savings maths is checked with a fake psutil (no real spawn), so
the numbers ``measure_standby`` reports on-device can be trusted. One real-psutil
smoke confirms the live path works against the actual process.
"""

import pytest

from core.power_report import footprint, savings, format_report, ProcFootprint


MB = 1_000_000


class _NoSuchProcess(Exception):
    def __init__(self, pid=None):
        self.pid = pid


class _Mem:
    def __init__(self, rss):
        self.rss = rss


class _Proc:
    def __init__(self, pid, rss_mb, threads=1, children=None, vanish=False):
        self.pid = pid
        self._rss = int(rss_mb * MB)
        self._threads = threads
        self._children = children or []
        self._vanish = vanish

    def memory_info(self):
        if self._vanish:
            raise _NoSuchProcess(self.pid)
        return _Mem(self._rss)

    def num_threads(self):
        if self._vanish:
            raise _NoSuchProcess(self.pid)
        return self._threads

    def children(self, recursive=True):
        return list(self._children)


class _Psutil:
    NoSuchProcess = _NoSuchProcess

    def __init__(self, root=None):
        self._root = root

    def Process(self, pid):
        if self._root is None or self._root.pid != pid:
            raise _NoSuchProcess(pid)
        return self._root


# ── footprint ────────────────────────────────────────────────────────── #

def test_footprint_sums_parent_and_children():
    root = _Proc(100, rss_mb=50, threads=8, children=[
        _Proc(200, rss_mb=1800, threads=40),   # the brain
        _Proc(300, rss_mb=5, threads=2),
    ])
    fp = footprint(100, psutil_mod=_Psutil(root))
    assert fp.rss_mb == pytest.approx(1855.0)
    assert fp.threads == 50
    assert fp.procs == 3


def test_footprint_without_children():
    root = _Proc(100, rss_mb=50, children=[_Proc(200, rss_mb=1800)])
    fp = footprint(100, psutil_mod=_Psutil(root), include_children=False)
    assert fp.rss_mb == pytest.approx(50.0)
    assert fp.procs == 1


def test_footprint_root_gone_is_zero():
    fp = footprint(999, psutil_mod=_Psutil(root=None))  # no such process
    assert fp == ProcFootprint(0.0, 0, 0)


def test_footprint_skips_a_child_that_vanishes_mid_sample():
    root = _Proc(100, rss_mb=50, children=[
        _Proc(200, rss_mb=1800),
        _Proc(300, rss_mb=99, vanish=True),  # dies between enumerate and sample
    ])
    fp = footprint(100, psutil_mod=_Psutil(root))
    assert fp.rss_mb == pytest.approx(1850.0)  # the vanished 99 MB not counted
    assert fp.procs == 2


# ── savings ──────────────────────────────────────────────────────────── #

def test_savings_delta_and_percent():
    dormant = ProcFootprint(rss_mb=50, threads=8, procs=1)
    resident = ProcFootprint(rss_mb=1855, threads=50, procs=3)
    s = savings(dormant, resident)
    assert s["rss_saved_mb"] == pytest.approx(1805.0)
    assert s["pct_saved"] == pytest.approx(97.3, abs=0.1)
    assert s["dormant_procs"] == 1 and s["resident_procs"] == 3


def test_savings_no_div_by_zero_when_resident_empty():
    s = savings(ProcFootprint(0, 0, 0), ProcFootprint(0, 0, 0))
    assert s["pct_saved"] == 0.0
    assert s["rss_saved_mb"] == 0.0


def test_format_report_mentions_the_numbers():
    s = savings(ProcFootprint(50, 8, 1), ProcFootprint(1850, 50, 3))
    text = format_report(s)
    assert "1800 MB" in text
    assert "%" in text and "dormant" in text.lower()


# ── real psutil smoke (the live path) ────────────────────────────────── #

def test_real_psutil_footprint_of_this_process():
    psutil = pytest.importorskip("psutil")
    import os
    fp = footprint(os.getpid())  # real psutil
    assert fp.rss_mb > 0
    assert fp.procs >= 1
