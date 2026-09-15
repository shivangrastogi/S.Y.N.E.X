"""Routine learner — turns presence history into *offers*, never actions.

Reads the append-only history written by ``core/presence_journal.py`` and
looks for stable daily rhythms: "you arrive and start a CODING session around
10:00 most weekdays", "you wind down ~22:30". When a pattern is consistent
enough across enough distinct days, it surfaces a ``Suggestion`` — a
ready-to-create automation routine the user can accept or dismiss.

Two hard rules, by design:

* **It only suggests.** Nothing here writes a routine or fires an action; the
  output is data the GUI turns into a yes/no card. Earned trust before
  automation.
* **It needs real evidence.** A pattern must recur on ``min_days`` distinct
  days within a tight time window before it's offered, so a couple of odd days
  never trigger a bogus suggestion.

Pure and dependency-free (just the journal records in, suggestions out) so it
unit-tests without a camera, a clock, or torch.

    from core.routine_learner import learn_from_journal
    for s in learn_from_journal():
        print(s.title, s.confidence, s.routine_spec)
"""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_MIN_DAYS = 4               # distinct days a pattern must recur on
_WINDOW_MIN = 45           # arrivals must cluster within ±this many minutes
_LOOKBACK_DAYS = 21        # only consider roughly the last few weeks


@dataclass(frozen=True)
class Suggestion:
    """A routine the learner thinks is worth offering."""
    key: str                       # stable id so the GUI can de-dupe/dismiss
    title: str                     # human, one line
    detail: str                    # why we're suggesting it
    confidence: float              # 0..1
    routine_spec: Dict[str, Any]   # ready for core.automation, if accepted
    evidence_days: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _circular_mean_minutes(minutes: List[int]) -> float:
    """Average a list of minute-of-day values (no midnight wrap handling
    needed for daytime arrivals, but we keep it simple and robust)."""
    return sum(minutes) / len(minutes) if minutes else 0.0


def _hhmm(total_min: float) -> str:
    h = int(total_min // 60) % 24
    m = int(round(total_min % 60))
    return f"{h:02d}:{m:02d}"


def learn_from_journal(records: Optional[List[Dict[str, Any]]] = None, *,
                       min_days: int = _MIN_DAYS,
                       window_min: int = _WINDOW_MIN,
                       now: Optional[datetime] = None) -> List[Suggestion]:
    """Analyse journal ``records`` and return zero or more suggestions.

    If ``records`` is None they're pulled from the live journal. Pass them in
    for tests.
    """
    if records is None:
        try:
            from core.presence_journal import get_journal
            records = get_journal().records()
        except Exception:
            return []

    now = now or datetime.now()
    suggestions: List[Suggestion] = []
    suggestions.extend(_learn_arrivals(records, min_days, window_min, now))
    suggestions.extend(_learn_winddown(records, min_days, window_min, now))
    return suggestions


def _learn_arrivals(records, min_days, window_min, now) -> List[Suggestion]:
    """Find a consistent weekday 'start work in PROFILE' time."""
    # profile → {date: earliest arrival minute-of-day}
    by_profile: Dict[str, Dict[str, int]] = defaultdict(dict)
    for r in records:
        if r.get("t") != "state":
            continue
        if r.get("prev") not in ("away", "idle"):
            continue
        if r.get("state") not in ("active", "focus"):
            continue
        dt = _parse_ts(r.get("ts", ""))
        if dt is None or (now - dt).days > _LOOKBACK_DAYS:
            continue
        if dt.weekday() >= 5:                      # weekdays only for work start
            continue
        profile = r.get("profile") or "ANY"
        day = dt.date().isoformat()
        mod = dt.hour * 60 + dt.minute
        # keep the earliest arrival per day (the "start of day")
        if day not in by_profile[profile] or mod < by_profile[profile][day]:
            by_profile[profile][day] = mod

    out: List[Suggestion] = []
    for profile, per_day in by_profile.items():
        if profile in ("IDLE", "ANY"):
            continue
        minutes = list(per_day.values())
        if len(minutes) < min_days:
            continue
        spread = statistics.pstdev(minutes) if len(minutes) > 1 else 0.0
        if spread > window_min:
            continue
        mean = _circular_mean_minutes(minutes)
        hhmm = _hhmm(mean)
        conf = max(0.0, min(1.0, 1.0 - spread / (2 * window_min)))
        out.append(Suggestion(
            key=f"arrival:{profile}:{hhmm}",
            title=f"Auto-start {profile.title()} mode at ~{hhmm} on weekdays?",
            detail=(f"You've begun a {profile.title()} session around {hhmm} on "
                    f"{len(minutes)} weekdays recently (±{int(spread)} min)."),
            confidence=round(conf, 2),
            evidence_days=len(minutes),
            routine_spec={
                "name": f"auto_{profile.lower()}_start",
                "description": f"Suggested from your {profile.title()} rhythm",
                "trigger": {"kind": "time", "params": {"cron": _cron_weekday(hhmm)}},
                "actions": [
                    {"kind": "notify",
                     "params": {"title": "A.E.R.I.S",
                                "body": f"{profile.title()} mode — ready when you are."}},
                ],
                "enabled": False,
            },
            meta={"profile": profile, "hhmm": hhmm, "spread_min": int(spread)},
        ))
    return out


def _learn_winddown(records, min_days, window_min, now) -> List[Suggestion]:
    """Find a consistent end-of-day 'last leave' time → offer a wind-down."""
    per_day: Dict[str, int] = {}
    for r in records:
        if r.get("t") != "state":
            continue
        if r.get("state") != "away" or r.get("prev") not in ("active", "focus"):
            continue
        dt = _parse_ts(r.get("ts", ""))
        if dt is None or (now - dt).days > _LOOKBACK_DAYS:
            continue
        if dt.hour < 18:                           # only evening departures
            continue
        day = dt.date().isoformat()
        mod = dt.hour * 60 + dt.minute
        if day not in per_day or mod > per_day[day]:   # latest leave that day
            per_day[day] = mod

    minutes = list(per_day.values())
    if len(minutes) < min_days:
        return []
    spread = statistics.pstdev(minutes) if len(minutes) > 1 else 0.0
    if spread > window_min:
        return []
    mean = _circular_mean_minutes(minutes)
    hhmm = _hhmm(mean)
    conf = max(0.0, min(1.0, 1.0 - spread / (2 * window_min)))
    return [Suggestion(
        key=f"winddown:{hhmm}",
        title=f"A wind-down summary around {hhmm}?",
        detail=(f"You usually wrap up near {hhmm} ({len(minutes)} days, "
                f"±{int(spread)} min). Want an end-of-day recap then?"),
        confidence=round(conf, 2),
        evidence_days=len(minutes),
        routine_spec={
            "name": "auto_wind_down",
            "description": "Suggested from your end-of-day rhythm",
            "trigger": {"kind": "time", "params": {"cron": _cron_daily(hhmm)}},
            "actions": [
                {"kind": "notify",
                 "params": {"title": "A.E.R.I.S",
                            "body": "Wrapping up? Here's your day at a glance."}},
            ],
            "enabled": False,
        },
        meta={"hhmm": hhmm, "spread_min": int(spread)},
    )]


def _cron_weekday(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(m)} {int(h)} * * 1-5"


def _cron_daily(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(m)} {int(h)} * * *"


if __name__ == "__main__":      # pragma: no cover — manual smoke
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for s in learn_from_journal():
        print(f"  • {s.title}  (conf {s.confidence}, {s.evidence_days}d)")
