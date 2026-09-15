"""Temporal recall (core.temporal_recall) — I2. Fakes + frozen clock."""
from datetime import datetime, date, timedelta

from core import temporal_recall as tr

# Sunday 2026-07-12, 15:00
_NOW = datetime(2026, 7, 12, 15, 0).timestamp()


# ── window parsing ────────────────────────────────────────────────────

def test_parse_kal_is_yesterday_for_recall():
    t0, t1, label = tr.parse_window("kal maine kya kiya tha", _NOW)
    assert label == "kal"
    assert datetime.fromtimestamp(t0).date() == date(2026, 7, 11)
    assert t1 - t0 == 86400.0


def test_parse_requires_ask_verb_not_command():
    assert tr.parse_window("kal alarm laga do", _NOW) is None      # command
    assert tr.parse_window("kal ka kya plan hai", _NOW) is None    # future-ask
    assert tr.parse_window("torch on karo", _NOW) is None


def test_parse_aaj_week_and_weekday():
    t0, _, label = tr.parse_window("aaj kya kiya maine", _NOW)
    assert label == "aaj" and datetime.fromtimestamp(t0).hour == 0
    t0, t1, label = tr.parse_window("pichhle hafte kitna kaam hua", _NOW)
    assert label == "pichhle hafte" and (t1 - t0) == 7 * 86400.0
    # Sunday se poocha "shukrawar" → most recent PAST Friday = July 10
    t0, _, label = tr.parse_window("shukrawar ko kya kiya tha", _NOW)
    assert datetime.fromtimestamp(t0).date() == date(2026, 7, 10)


# ── digest composition ────────────────────────────────────────────────

class FakeJournal:
    def day_summary(self, day):
        return {"focus_s": 5400, "active_s": 3600, "arrivals": 1}


class _G:
    def __init__(self, text, state, updated):
        self.text, self.state, self.updated = text, state, updated


class FakeGoals:
    def __init__(self, goals):
        self._g = goals

    def all(self):
        return self._g


class FakeLedger:
    def __init__(self, entries):
        self._e = entries

    def all(self):
        return self._e


def test_digest_composes_all_sources():
    t0 = datetime(2026, 7, 11).timestamp()
    out = tr.digest(t0, t0 + 86400, "kal",
                    journal=FakeJournal(),
                    goal_store=FakeGoals([_G("rahul follow up", "done",
                                             t0 + 3600)]),
                    ledger=FakeLedger([{"ts": t0 + 100, "action": "torch_on",
                                        "decision": "allow"}]))
    assert out.startswith("Kal:")
    assert "1.5 ghante focus" in out
    assert "rahul follow up" in out
    assert "torch_on" in out


def test_digest_empty_window_is_honest():
    t0 = datetime(2026, 7, 11).timestamp()
    out = tr.digest(t0, t0 + 86400, "kal", journal=None,
                    goal_store=FakeGoals([]), ledger=FakeLedger([]))
    assert "koi record nahi" in out


def test_answer_end_to_end():
    out = tr.answer("kal maine kya kiya tha?", _NOW, journal=FakeJournal(),
                    goal_store=FakeGoals([]), ledger=FakeLedger([]))
    assert out is not None and out.startswith("Kal:")
    assert tr.answer("gaana chala do", _NOW) is None
