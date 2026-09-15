"""Tests for StandbyJournal — the capped, persisted standby event log."""

import json
import threading

import pytest

from core.standby_journal import StandbyJournal, JournalEvent
from core.standby_orchestrator import StandbyState


class _Clock:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class _Disk:
    def __init__(self, seed=None):
        self.files = dict(seed or {})

    def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def write(self, path, text):
        self.files[path] = text


# ── recording / ring buffer ──────────────────────────────────────────── #

def test_record_and_recent():
    j = StandbyJournal()
    j.record("wake")
    j.record("spinup", "cold")
    evs = j.recent(10)
    assert [e.kind for e in evs] == ["wake", "spinup"]
    assert evs[1].detail == "cold"


def test_capacity_caps_oldest_out():
    j = StandbyJournal(capacity=3)
    for i in range(5):
        j.record(f"e{i}")
    kinds = [e.kind for e in j.all()]
    assert kinds == ["e2", "e3", "e4"]     # oldest two dropped


def test_recent_returns_only_last_n():
    j = StandbyJournal()
    for i in range(10):
        j.record(f"e{i}")
    assert [e.kind for e in j.recent(3)] == ["e7", "e8", "e9"]


def test_recent_zero_is_empty():
    j = StandbyJournal()
    j.record("wake")
    assert j.recent(0) == []


def test_on_state_change_maps_to_spinup_spindown():
    j = StandbyJournal()
    j.on_state_change(StandbyState.ACTIVE)
    j.on_state_change(StandbyState.DORMANT)
    assert [e.kind for e in j.all()] == ["spinup", "spindown"]


def test_count_by_kind_and_total():
    j = StandbyJournal()
    j.record("wake"); j.record("wake"); j.record("spinup")
    assert j.count("wake") == 2
    assert j.count("spinup") == 1
    assert j.count() == 3


# ── formatting ───────────────────────────────────────────────────────── #

def test_format_recent_shows_relative_time_and_detail():
    clk = _Clock()
    j = StandbyJournal(now=clk)
    j.record("crash", "brain died")
    clk.advance(125)                        # 2m 5s later
    lines = j.format_recent(5)
    assert "crash (brain died)" in lines[0]
    assert "2m ago" in lines[0]


# ── summary + kind filtering (journalctl-style) ──────────────────────── #

def test_summary_counts_per_kind():
    j = StandbyJournal()
    j.record("wake"); j.record("wake"); j.record("spinup"); j.record("crash")
    assert j.summary() == {"wake": 2, "spinup": 1, "crash": 1}


def test_summary_empty_journal():
    assert StandbyJournal().summary() == {}


def test_recent_filters_by_kind():
    j = StandbyJournal()
    j.record("wake"); j.record("spinup"); j.record("wake"); j.record("crash")
    kinds = [e.kind for e in j.recent(10, kind="wake")]
    assert kinds == ["wake", "wake"]


def test_recent_kind_not_present_is_empty():
    j = StandbyJournal()
    j.record("wake")
    assert j.recent(10, kind="crash") == []


def test_format_recent_filtered_by_kind():
    clk = _Clock()
    j = StandbyJournal(now=clk)
    j.record("wake"); j.record("crash", "died"); j.record("wake")
    lines = j.format_recent(10, kind="crash")
    assert len(lines) == 1
    assert "crash (died)" in lines[0]


def test_recent_kind_respects_limit():
    j = StandbyJournal()
    for _ in range(5):
        j.record("wake")
    j.record("crash")
    assert len(j.recent(2, kind="wake")) == 2   # last 2 of the 5 wakes


# ── persistence ──────────────────────────────────────────────────────── #

def test_flush_and_load_round_trip():
    disk = _Disk()
    j = StandbyJournal(path="j.json", read=disk.read, write=disk.write)
    j.record("wake"); j.record("spinup", "x")
    j.flush()
    # a fresh journal loads the same events off the (in-memory) disk
    j2 = StandbyJournal(path="j.json", read=disk.read, write=disk.write)
    j2.load()
    assert [(e.kind, e.detail) for e in j2.all()] == [("wake", ""), ("spinup", "x")]


def test_flush_without_path_is_noop():
    j = StandbyJournal()               # no path
    j.record("wake")
    j.flush()                          # must not raise (nowhere to write)


def test_load_missing_file_is_empty():
    disk = _Disk()
    j = StandbyJournal(path="nope.json", read=disk.read, write=disk.write)
    j.load()
    assert j.all() == []


def test_load_corrupt_file_is_empty():
    disk = _Disk({"j.json": "{not json"})
    j = StandbyJournal(path="j.json", read=disk.read, write=disk.write)
    j.load()
    assert j.all() == []


def test_load_non_list_is_empty():
    disk = _Disk({"j.json": json.dumps({"not": "a list"})})
    j = StandbyJournal(path="j.json", read=disk.read, write=disk.write)
    j.load()
    assert j.all() == []


def test_load_skips_garbage_entries():
    disk = _Disk({"j.json": json.dumps([
        {"ts": 1.0, "kind": "wake", "detail": ""},
        "not a dict",
        {"ts": "bad"},                 # from_dict coerces → ts 0, kind '?'
    ])})
    j = StandbyJournal(path="j.json", read=disk.read, write=disk.write)
    j.load()
    kinds = [e.kind for e in j.all()]
    assert "wake" in kinds
    assert "not a dict" not in kinds   # the string entry is dropped


def test_from_dict_rejects_non_dict():
    assert JournalEvent.from_dict("x") is None
    assert JournalEvent.from_dict(None) is None


def test_load_after_flush_respects_capacity_on_reload():
    disk = _Disk()
    j = StandbyJournal(capacity=100, path="j.json", read=disk.read, write=disk.write)
    for i in range(10):
        j.record(f"e{i}")
    j.flush()
    small = StandbyJournal(capacity=3, path="j.json", read=disk.read, write=disk.write)
    small.load()
    assert [e.kind for e in small.all()] == ["e7", "e8", "e9"]  # capped on load


# ── thread safety ────────────────────────────────────────────────────── #

def test_concurrent_record_loses_nothing():
    j = StandbyJournal(capacity=100000)
    threads, per = 8, 1000
    barrier = threading.Barrier(threads)

    def hammer():
        barrier.wait()
        for _ in range(per):
            j.record("wake")

    ts = [threading.Thread(target=hammer) for _ in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert j.count() == threads * per
