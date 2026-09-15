"""Tests for core.presence_journal — the persistent presence history."""
import os
import tempfile

import core.presence_journal as pj


def _journal():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)                      # start clean; module creates on append
    return pj.PresenceJournal(path=path), path


def test_append_and_read_back():
    j, path = _journal()
    try:
        j.record_state("active", prev="away", held_s=120, profile="CODING")
        j.record_moment("greeting", "Hi", priority=1, state="active")
        recs = j.records()
        assert len(recs) == 2
        assert recs[0]["t"] == "state" and recs[0]["state"] == "active"
        assert recs[1]["t"] == "moment" and recs[1]["kind"] == "greeting"
    finally:
        os.path.exists(path) and os.remove(path)


def test_transitions_filters_states_only():
    j, path = _journal()
    try:
        j.record_state("active", prev="away", held_s=10)
        j.record_moment("farewell", "bye", priority=0)
        j.record_state("away", prev="active", held_s=30)
        ts = j.transitions()
        assert len(ts) == 2
        assert {t["state"] for t in ts} == {"active", "away"}
    finally:
        os.path.exists(path) and os.remove(path)


def test_day_summary_aggregates_today():
    j, path = _journal()
    try:
        # away->active (arrival), active->focus, focus->away
        j.record_state("active", prev="away", held_s=300, profile="CODING")
        j.record_state("focus", prev="active", held_s=600, profile="CODING")
        j.record_state("away", prev="focus", held_s=1200, profile="IDLE")
        j.record_moment("greeting", "gm", priority=1, state="active")
        s = j.day_summary()
        assert s["arrivals"] == 1            # away->active counts
        assert s["focus_s"] == 1200          # the held_s when leaving focus
        assert s["active_s"] == 600          # held_s when leaving active
        assert s["moments"].get("greeting") == 1
    finally:
        os.path.exists(path) and os.remove(path)


def test_digest_line_empty_when_no_activity():
    j, path = _journal()
    try:
        assert j.digest_line() == ""
        j.record_state("active", prev="away", held_s=600, profile="CODING")
        j.record_state("away", prev="active", held_s=10, profile="IDLE")
        assert "screen pe" in j.digest_line()
    finally:
        os.path.exists(path) and os.remove(path)


def test_trim_keeps_recent(tmp_path):
    path = str(tmp_path / "j.jsonl")
    j = pj.PresenceJournal(path=path, max_lines=200)
    for i in range(900):
        j.record_state("active", prev="away", held_s=i)
    # appends_since_trim trips _maybe_trim once past _TRIM_SLACK; final count
    # should be bounded well under what we wrote.
    assert len(j.records()) <= 200 + pj._TRIM_SLACK
