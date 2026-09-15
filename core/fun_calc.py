"""Days-until-weekend + Scrabble word score. Pure math, offline."""
from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

_WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
       "Saturday", "Sunday"]


def weekend_countdown(text: str, today: Optional[_dt.date] = None) -> Optional[str]:
    today = today or _dt.date.today()
    wd = today.weekday()          # Mon=0 .. Sun=6
    if wd == 5:
        return "Aaj Saturday hai — weekend shuru! Kal Sunday bhi hai."
    if wd == 6:
        return "Aaj Sunday hai — weekend ka aakhri din. Kal se kaam."
    days_to_sat = (5 - wd) % 7
    sat = today + _dt.timedelta(days=days_to_sat)
    day_word = "din" if days_to_sat == 1 else "din"
    return (f"Weekend (Saturday) me {days_to_sat} {day_word} baaki "
            f"({sat.strftime('%A %d %B')}). Aaj {_WD[wd]} hai.")


_SCRABBLE = {}
for _pts, _letters in {
    1: "eaionrtlsu", 2: "dg", 3: "bcmp", 4: "fhvwy",
    5: "k", 8: "jx", 10: "qz",
}.items():
    for _c in _letters:
        _SCRABBLE[_c] = _pts

_CMD_WORDS = {"scrabble", "score", "ka", "ki", "ke", "value", "points",
              "point", "nikaalo", "nikalo", "batao", "word", "of", "for",
              "kitna", "kitne", "hai", "the"}


def scrabble_score(text: str) -> Optional[str]:
    # quoted word wins; else the longest alphabetic non-command token
    q = re.search(r"[\"'“”‘’]([A-Za-z]+)[\"'“”‘’]", text or "")
    if q:
        word = q.group(1)
    else:
        toks = re.findall(r"[A-Za-z]+", text or "")
        cands = [w for w in toks if w.lower() not in _CMD_WORDS]
        if not cands:
            return ("Kaunsa word? Jaise 'scrabble score of QUIZ' — "
                    "main letter points jod dunga.")
        word = max(cands, key=len)
    total = sum(_SCRABBLE.get(c, 0) for c in word.lower())
    breakdown = "+".join(f"{c.upper()}{_SCRABBLE.get(c, 0)}" for c in word.lower())
    return f"'{word.upper()}' Scrabble score: {total} ({breakdown})."


def week_number(text: str, today: Optional[_dt.date] = None) -> Optional[str]:
    """ISO week number + day-of-year for a date (or today)."""
    from core.misc_calc import _MONTHS
    t = (text or "").lower()
    today = today or _dt.date.today()
    d = None
    m = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b", t)
    if m:
        try:
            d = _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return "Tareekh sahi nahi — jaise '15/08/2026'."
    else:
        mon = next((v for k, v in _MONTHS.items() if re.search(rf"\b{k}\b", t)), None)
        ym = re.search(r"\b(\d{4})\b", t)
        dd = re.search(r"\b(\d{1,2})\b", t)
        if mon and ym and dd:
            try:
                d = _dt.date(int(ym.group(1)), mon, int(dd.group(1)))
            except ValueError:
                return "Tareekh sahi nahi — jaise '15 august 2026'."
    d = d or today
    iso_year, iso_week, iso_wd = d.isocalendar()
    doy = d.timetuple().tm_yday
    total = 366 if (d.year % 4 == 0 and (d.year % 100 or d.year % 400 == 0)) else 365
    left = total - doy
    when = "Aaj" if d == today else d.strftime("%d %B %Y")
    return (f"{when}: saal ka week {iso_week} (ISO), din {doy}/{total} "
            f"({left} din baaki saal me).")


def ordinal_number(text: str) -> Optional[str]:
    """Turn a number into its ordinal form. '23' -> '23rd'."""
    m = re.search(r"\b(\d{1,9})\b", text or "")
    if not m:
        return ("Kaunsa number? Jaise '23 ka ordinal' = 23rd.")
    n = int(m.group(1))
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n} -> {n}{suf}."


_DUR_UNIT = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1, "s": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600, "ghante": 3600,
    "day": 86400, "days": 86400, "din": 86400,
}


def duration_humanize(text: str) -> Optional[str]:
    """Break a raw duration into days/hours/minutes/seconds.
    '9000 seconds' -> '2 hr 30 min'."""
    t = (text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|"
                  r"hrs?|ghante|days?|din|\bs\b)", t)
    if not m:
        return ("Number aur unit do — jaise '9000 seconds' ya '150 minutes' — "
                "main ghante/minute me tod dunga.")
    total = float(m.group(1)) * _DUR_UNIT.get(m.group(2), 1)
    total = int(round(total))
    if total <= 0:
        return "Duration positive hona chahiye."
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    mi, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d} day{'s' if d > 1 else ''}")
    if h:
        parts.append(f"{h} hr")
    if mi:
        parts.append(f"{mi} min")
    if s:
        parts.append(f"{s} sec")
    return f"{m.group(1)} {m.group(2)} = " + " ".join(parts) + "."


def next_birthday(text: str, today: Optional[_dt.date] = None) -> Optional[str]:
    """Days until the next birthday (+ turning age if year given)."""
    from core.misc_calc import _MONTHS
    t = (text or "").lower()
    today = today or _dt.date.today()
    day = month = year = None
    m = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{4}))?\b", t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else None
    else:
        month = next((v for k, v in _MONTHS.items() if re.search(rf"\b{k}\b", t)), None)
        dd = re.search(r"\b(\d{1,2})\b", t)
        ym = re.search(r"\b(\d{4})\b", t)
        if month and dd:
            day = int(dd.group(1))
            year = int(ym.group(1)) if ym else None
    if not day or not month or not (1 <= month <= 12 and 1 <= day <= 31):
        return ("Apni janam-tareekh do — jaise '15 august' ya '15/08/1998' — "
                "main next birthday tak ke din bata dunga.")

    def _mk(yr):
        try:
            return _dt.date(yr, month, day)
        except ValueError:              # Feb 29 in a non-leap year
            return _dt.date(yr, month, 28)
    nb = _mk(today.year)
    if nb < today:
        nb = _mk(today.year + 1)
    days = (nb - today).days
    when = nb.strftime("%d %B %Y")
    if days == 0:
        base = "Aaj hi birthday hai! Happy birthday."
    else:
        base = f"Next birthday {when} ko — {days} din baaki."
    if year:
        turning = nb.year - year
        base += f" (aap {turning} saal ke ho jaoge)."
    return base
