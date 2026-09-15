"""Tests for the World Model (core.world_model) — Q2·M4. Fakes, no engine."""

from datetime import datetime

from core.world_model import (
    Situation,
    WorldModel,
    situation_initiatives,
)


class _G:
    def __init__(self, gid, text, state="acting", blocker=None, ask=None):
        self.id, self.text, self.state = gid, text, state
        self.blocker, self.ask = blocker, ask


class FakeGoals:
    def __init__(self, goals, due=None):
        self._g = goals
        self._due = due or []

    def open_goals(self):
        return self._g

    def due(self, t=None):
        return self._due


class FakeGate:
    def __init__(self, panic=False, quiet=False):
        self._panic, self._quiet = panic, quiet

    def _is_panic(self):
        return self._panic

    def _in_quiet(self, t):
        return self._quiet


class FakePower:
    """snapshot() → object with percent / on_battery / plugged."""
    def __init__(self, percent=100, on_battery=False, plugged=True):
        from types import SimpleNamespace
        self._s = SimpleNamespace(percent=percent, on_battery=on_battery,
                                  plugged=plugged)

    def snapshot(self):
        return self._s


class FakePresence:
    """state_records() → chronological state dicts (last = current)."""
    def __init__(self, records=None):
        self._r = records or []

    def state_records(self, *, limit=None):
        return self._r


def _wm(goals=None, panic=False, quiet=False, now=None, due=None,
        power=None, presence=None):
    return WorldModel(
        goals_provider=lambda: FakeGoals(goals or [], due),
        gate_provider=lambda: FakeGate(panic, quiet),
        power_provider=lambda: power or FakePower(),      # plugged, 100% by default
        presence_provider=lambda: presence or FakePresence(),  # no focus by default
        now_fn=(lambda: now) if now else __import__("time").time)


def _at(h):
    return datetime(2026, 7, 12, h, 0).timestamp()  # 2026-07-12 = Sunday


# ── situation snapshot ─────────────────────────────────────────────

def test_part_of_day_and_weekday():
    assert _wm(now=_at(8)).situation().part_of_day == "subah"
    assert _wm(now=_at(14)).situation().part_of_day == "dopahar"
    assert _wm(now=_at(19)).situation().part_of_day == "shaam"
    assert _wm(now=_at(23)).situation().part_of_day == "raat"
    assert _wm(now=_at(8)).situation().weekday == "Ravivar"


def test_counts_open_goals_and_awaiting_user():
    goals = [
        _G("g1", "plan trip", "acting"),
        _G("g2", "confirm delete", "blocked", "need_user", "Pakka?"),
        _G("g3", "later", "blocked", "need_time"),
    ]
    st = _wm(goals=goals, now=_at(10)).situation()
    assert st.open_goals == 3
    assert len(st.awaiting_user) == 1
    assert st.awaiting_user[0]["ask"] == "Pakka?"


def test_panic_and_quiet_flags():
    st = _wm(panic=True, quiet=True, now=_at(2)).situation()
    assert st.awake is False and st.quiet_hours is True


def test_survives_missing_providers():
    wm = WorldModel(goals_provider=lambda: (_ for _ in ()).throw(Exception()),
                    gate_provider=lambda: (_ for _ in ()).throw(Exception()),
                    now_fn=lambda: _at(9))
    st = wm.situation()
    assert isinstance(st, Situation) and st.open_goals == 0


# ── situation → initiative candidates ──────────────────────────────

def test_situation_initiatives_from_awaiting_goal():
    goals = [_G("g2", "confirm delete", "blocked", "need_user", "Pakka?")]
    cands = situation_initiatives(_wm(goals=goals, now=_at(10)))
    assert len(cands) == 1
    assert cands[0].kind == "goal_needs_you"
    assert cands[0].source_id == "await:g2"
    assert cands[0].text == "Pakka?"


def test_no_awaiting_goals_no_candidates():
    goals = [_G("g1", "plan", "acting")]
    assert situation_initiatives(_wm(goals=goals, now=_at(10))) == []


# ── enriched surroundings: battery, focus, due goals ───────────────────

def _focus_record(minutes_ago, now):
    ts = datetime.fromtimestamp(now - minutes_ago * 60).isoformat()
    return {"t": "state", "ts": ts, "state": "focus"}


def test_situation_captures_battery_and_focus():
    now = _at(15)
    st = _wm(now=now, power=FakePower(percent=42, on_battery=True, plugged=False),
             presence=FakePresence([_focus_record(30, now)])).situation()
    assert st.battery == {"percent": 42, "on_battery": True, "plugged": False}
    assert st.focus_min == 30


def test_focus_zero_when_not_currently_focusing():
    now = _at(15)
    recs = [{"t": "state", "ts": datetime.fromtimestamp(now - 600).isoformat(),
             "state": "active"}]                     # last state != focus
    st = _wm(now=now, presence=FakePresence(recs)).situation()
    assert st.focus_min == 0


def test_due_goals_are_observable_state_not_re_emitted():
    # Due need_time goals show up in the situation snapshot as data, but the
    # World Model does NOT emit an initiative for them — the Initiative Engine's
    # own built-in due source owns that (no double nudge).
    due = [_G("g9", "check cricket score")]
    wm = _wm(now=_at(16), due=due)
    assert [d["id"] for d in wm.situation().due_goals] == ["g9"]
    assert not any(c.kind == "goal_due" for c in situation_initiatives(wm))


def test_low_battery_surfaces_only_when_on_battery():
    now = _at(16)
    # 15% but plugged in → no nudge
    assert situation_initiatives(
        _wm(now=now, power=FakePower(15, on_battery=False, plugged=True))) == []
    # 15% on battery → nudge, and crit bucket at <=10
    low = situation_initiatives(_wm(now=now, power=FakePower(15, on_battery=True,
                                                             plugged=False)))
    assert low and low[0].kind == "battery_low"
    assert low[0].source_id == "battery:low"
    crit = situation_initiatives(_wm(now=now, power=FakePower(8, on_battery=True,
                                                              plugged=False)))
    assert crit[0].source_id == "battery:crit"


def test_long_focus_earns_a_break_nudge():
    now = _at(15)
    # 100 min continuous focus → break nudge; 30 min → none
    long = situation_initiatives(
        _wm(now=now, presence=FakePresence([_focus_record(100, now)])))
    assert any(c.kind == "take_break" and c.source_id == "break:focus"
               for c in long)
    short = situation_initiatives(
        _wm(now=now, presence=FakePresence([_focus_record(30, now)])))
    assert not any(c.kind == "take_break" for c in short)
