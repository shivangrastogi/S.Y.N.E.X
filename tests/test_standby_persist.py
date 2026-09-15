"""Tests for lifetime standby persistence (LifetimeStats + StandbyStatsStore).

The store's IO is injected with an in-memory dict acting as "disk", so the
accounting and load/commit flow are checked without touching the real
filesystem. One test exercises the real atomic writer via pytest's tmp_path.
"""

import json

import pytest

from core.standby_persist import LifetimeStats, StandbyStatsStore


# A StandbyStats.snapshot()-shaped session dict.
def _session(active=10.0, dormant=90.0, wakes=3, spinups=1):
    return {"active_s": active, "dormant_s": dormant,
            "wakes": wakes, "spinups": spinups}


# ── LifetimeStats (pure) ─────────────────────────────────────────────── #

def test_merge_session_adds_and_counts():
    lt = LifetimeStats().merge_session(_session(10, 90, 3, 1))
    assert lt.active_s == 10.0
    assert lt.dormant_s == 90.0
    assert lt.wakes == 3
    assert lt.spinups == 1
    assert lt.sessions == 1


def test_merge_two_sessions_accumulates():
    lt = LifetimeStats().merge_session(_session(10, 90)).merge_session(_session(20, 80))
    assert lt.active_s == 30.0
    assert lt.dormant_s == 170.0
    assert lt.sessions == 2


def test_snapshot_dormant_pct():
    lt = LifetimeStats(active_s=10.0, dormant_s=90.0)
    assert lt.snapshot()["lifetime_dormant_pct"] == 90.0


def test_snapshot_empty_is_fully_dormant():
    assert LifetimeStats().snapshot()["lifetime_dormant_pct"] == 100.0


def test_merge_tolerates_missing_and_bad_fields():
    lt = LifetimeStats().merge_session({"active_s": "oops", "wakes": None})
    assert lt.active_s == 0.0      # bad type → 0
    assert lt.dormant_s == 0.0     # missing → 0
    assert lt.wakes == 0
    assert lt.sessions == 1        # still counts as a session


def test_merge_none_snapshot_counts_session():
    lt = LifetimeStats(sessions=2).merge_session(None)
    assert lt.sessions == 3


# ── (de)serialisation robustness ─────────────────────────────────────── #

def test_to_from_dict_round_trip():
    lt = LifetimeStats(active_s=5.0, dormant_s=95.0, wakes=7, spinups=2, sessions=4)
    assert LifetimeStats.from_dict(lt.to_dict()) == lt


def test_from_dict_rejects_non_dict():
    assert LifetimeStats.from_dict("not a dict") == LifetimeStats()
    assert LifetimeStats.from_dict(None) == LifetimeStats()


def test_from_dict_tolerates_garbage_values():
    lt = LifetimeStats.from_dict({"active_s": "x", "dormant_s": -5, "sessions": "3"})
    assert lt.active_s == 0.0
    assert lt.dormant_s == 0.0      # negative rejected
    assert lt.sessions == 3         # numeric string coerced


# ── StandbyStatsStore (injected in-memory disk) ──────────────────────── #

class _Disk:
    """A fake filesystem: one path → text."""

    def __init__(self, seed=None):
        self.files = dict(seed or {})
        self.writes = 0

    def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def write(self, path, text):
        self.files[path] = text
        self.writes += 1


def _store(disk):
    return StandbyStatsStore("stats.json", read=disk.read, write=disk.write)


def test_load_missing_file_is_empty_baseline():
    store = _store(_Disk())
    assert store.load() == LifetimeStats()


def test_load_corrupt_file_is_empty_baseline():
    store = _store(_Disk({"stats.json": "{not valid json"}))
    assert store.load() == LifetimeStats()   # no crash, fresh start


def test_load_reads_persisted_baseline():
    seed = json.dumps(LifetimeStats(active_s=1, dormant_s=99, sessions=5).to_dict())
    store = _store(_Disk({"stats.json": seed}))
    lt = store.load()
    assert lt.dormant_s == 99.0
    assert lt.sessions == 5


def test_commit_writes_baseline_plus_session():
    disk = _Disk()
    store = _store(disk)
    store.load()                       # empty baseline
    merged = store.commit(_session(10, 90, 3, 1))
    assert merged.active_s == 10.0
    assert merged.sessions == 1
    # persisted to disk
    on_disk = LifetimeStats.from_dict(json.loads(disk.files["stats.json"]))
    assert on_disk == merged


def test_repeated_commit_does_not_double_count():
    # A periodic checkpoint + a final flush of the SAME session must not add
    # the session twice — commit always recomputes from the fixed baseline.
    disk = _Disk()
    store = _store(disk)
    store.load()
    store.commit(_session(5, 5, 1, 1))          # checkpoint mid-session
    final = store.commit(_session(10, 90, 3, 1))  # session grew, final flush
    assert final.active_s == 10.0     # NOT 15
    assert final.dormant_s == 90.0
    assert final.sessions == 1        # still one session


def test_commit_accumulates_across_store_restarts():
    # Session 1 commits, then a NEW store loads that file and commits session 2.
    disk = _Disk()
    s1 = _store(disk); s1.load(); s1.commit(_session(10, 90, 2, 1))
    s2 = _store(disk); s2.load(); merged = s2.commit(_session(20, 80, 3, 1))
    assert merged.active_s == 30.0
    assert merged.dormant_s == 170.0
    assert merged.wakes == 5
    assert merged.sessions == 2


# ── real atomic writer (touches tmp_path only) ───────────────────────── #

def test_default_atomic_writer_round_trip(tmp_path):
    path = str(tmp_path / "nested" / "standby_stats.json")  # parent auto-created
    store = StandbyStatsStore(path)
    store.load()                       # missing → empty
    store.commit(_session(10, 90, 4, 2))
    # a fresh store reads it straight back off real disk
    reloaded = StandbyStatsStore(path).load()
    assert reloaded.active_s == 10.0
    assert reloaded.dormant_s == 90.0
    assert reloaded.wakes == 4
    assert reloaded.sessions == 1
