"""Date/time intelligence — world clock, date math, countdowns. All stdlib.

zoneinfo (Python 3.9+) ships the full IANA timezone database, so world
times need NO network. Date parsing is a small hand-rolled parser (no
dateutil dependency) tuned for the Hinglish forms a user actually speaks.
"""
from __future__ import annotations

import calendar
import datetime as _dt
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


# ── world clock ──────────────────────────────────────────────────────── #

# Spoken city / country → IANA zone. Small, curated; zoneinfo has the rest.
_CITY_ZONE: dict[str, str] = {
    "london": "Europe/London", "uk": "Europe/London", "england": "Europe/London",
    "new york": "America/New_York", "nyc": "America/New_York",
    "usa": "America/New_York", "us": "America/New_York",
    "america": "America/New_York", "washington": "America/New_York",
    "california": "America/Los_Angeles", "la": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "chicago": "America/Chicago", "texas": "America/Chicago",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "dubai": "Asia/Dubai", "uae": "Asia/Dubai",
    "singapore": "Asia/Singapore", "sydney": "Australia/Sydney",
    "australia": "Australia/Sydney", "melbourne": "Australia/Melbourne",
    "paris": "Europe/Paris", "france": "Europe/Paris",
    "berlin": "Europe/Berlin", "germany": "Europe/Berlin",
    "moscow": "Europe/Moscow", "russia": "Europe/Moscow",
    "china": "Asia/Shanghai", "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai", "hong kong": "Asia/Hong_Kong",
    "toronto": "America/Toronto", "canada": "America/Toronto",
    "india": "Asia/Kolkata", "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata",
    "nepal": "Asia/Kathmandu", "pakistan": "Asia/Karachi",
    "bangladesh": "Asia/Dhaka", "sri lanka": "Asia/Colombo",
    "saudi": "Asia/Riyadh", "riyadh": "Asia/Riyadh", "qatar": "Asia/Qatar",
    "brazil": "America/Sao_Paulo", "south africa": "Africa/Johannesburg",
}


def world_time(place: str) -> Optional[str]:
    """Current time in a named city/country. None if unknown."""
    try:
        from zoneinfo import ZoneInfo
    except Exception:
        return None
    p = (place or "").strip().lower()
    zone_name = _CITY_ZONE.get(p)
    if not zone_name:
        # Try an exact IANA name or a fuzzy city match ("kolkata" → Asia/Kolkata)
        try:
            from zoneinfo import available_timezones
            zl = p.replace(" ", "_")
            for z in available_timezones():
                if z.lower() == p or z.split("/")[-1].lower() == zl:
                    zone_name = z
                    break
        except Exception:
            pass
    if not zone_name:
        return None
    try:
        now = _dt.datetime.now(ZoneInfo(zone_name))
    except Exception:
        return None
    ist = _dt.datetime.now(ZoneInfo("Asia/Kolkata"))
    diff_h = (now.utcoffset().total_seconds()
              - ist.utcoffset().total_seconds()) / 3600
    rel = ("same as India" if abs(diff_h) < 0.01
           else f"{abs(diff_h):.0f}h {'ahead of' if diff_h > 0 else 'behind'} India")
    return (f"{place.title()} mein abhi "
            f"{now.strftime('%I:%M %p, %A').lstrip('0')} hai ({rel}).")


# ── date parsing (light, Hinglish-aware) ─────────────────────────────── #

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

# Fixed-date occasions (year-independent). Moving festivals (diwali/holi/eid)
# change yearly — we ask for a date rather than guess wrong.
_FIXED_DATES: dict[str, tuple[int, int]] = {
    "new year": (1, 1), "new years": (1, 1), "naya saal": (1, 1),
    "republic day": (1, 26), "gantantra diwas": (1, 26),
    "valentine": (2, 14), "valentines": (2, 14),
    "independence day": (8, 15), "swatantrata diwas": (8, 15),
    "gandhi jayanti": (10, 2),
    "christmas": (12, 25), "xmas": (12, 25),
    "new year eve": (12, 31),
}


def parse_date(text: str, base: Optional[_dt.date] = None) -> Optional[_dt.date]:
    """Parse a spoken date into a date. Handles '15 august [2027]',
    'august 15', '25/12', 'christmas', and fixed occasions. Year defaults
    to the NEXT occurrence (a countdown target should be in the future)."""
    base = base or _dt.date.today()
    t = (text or "").strip().lower()

    for name, (mm, dd) in _FIXED_DATES.items():
        if name in t:
            year = base.year
            cand = _dt.date(year, mm, dd)
            return cand if cand >= base else _dt.date(year + 1, mm, dd)

    # numeric dd/mm[/yyyy] or dd-mm
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        dd, mm = int(m.group(1)), int(m.group(2))
        yy = m.group(3)
        try:
            if yy:
                year = int(yy) + (2000 if len(yy) == 2 else 0)
                return _dt.date(year, mm, dd)
            cand = _dt.date(base.year, mm, dd)
            return cand if cand >= base else _dt.date(base.year + 1, mm, dd)
        except ValueError:
            return None

    # "15 august [2027]" or "august 15"
    m = re.search(r"\b(\d{1,2})\s+([a-z]{3,9})\b(?:\s+(\d{4}))?", t)
    if not m:
        m2 = re.search(r"\b([a-z]{3,9})\s+(\d{1,2})\b(?:\s+(\d{4}))?", t)
        if m2:
            month_name, day, yr = m2.group(1), int(m2.group(2)), m2.group(3)
            mm = _MONTHS.get(month_name)
            if mm:
                m = None
                year = int(yr) if yr else base.year
                try:
                    cand = _dt.date(year, mm, day)
                    if not yr and cand < base:
                        cand = _dt.date(year + 1, mm, day)
                    return cand
                except ValueError:
                    return None
    if m:
        day, month_name, yr = int(m.group(1)), m.group(2), m.group(3)
        mm = _MONTHS.get(month_name)
        if mm:
            year = int(yr) if yr else base.year
            try:
                cand = _dt.date(year, mm, day)
                if not yr and cand < base:
                    cand = _dt.date(year + 1, mm, day)
                return cand
            except ValueError:
                return None
    return None


# ── date math ("aaj se 45 din baad") ─────────────────────────────────── #

_NUM_WORDS = {"ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5,
              "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10}


def _num(text: str) -> Optional[int]:
    m = re.search(r"\b(\d+)\b", text)
    if m:
        return int(m.group(1))
    for w, n in _NUM_WORDS.items():
        if re.search(rf"\b{w}\b", text):
            return n
    return None


def date_math(text: str, base: Optional[_dt.date] = None) -> Optional[str]:
    """'aaj se 45 din baad', '3 hafte baad', '2 mahine pehle'."""
    base = base or _dt.date.today()
    t = (text or "").strip().lower()
    n = _num(t)
    if n is None:
        return None
    # Guard absurd values (a 200-digit "number" from garbage input would
    # overflow date arithmetic). Any date whose year would leave the
    # supported 1..9999 range is not a real question — reject uniformly.
    _TOO_FAR = "Itni door ki date nikaalna sensible nahi, sir — chhota number bolo."
    if n > 3_000_000:
        return _TOO_FAR
    back = bool(re.search(r"\b(pehle|pahle|before|ago|peeche)\b", t))
    sign = -1 if back else 1
    try:
        if re.search(r"\b(hafte|hafta|week|weeks|saptah)\b", t):
            delta = _dt.timedelta(weeks=n)
            unit = f"{n} hafte"
        elif re.search(r"\b(mahine|mahina|month|months|maah)\b", t):
            # add months by calendar arithmetic
            month0 = base.month - 1 + sign * n
            year = base.year + month0 // 12
            month = month0 % 12 + 1
            day = min(base.day, calendar.monthrange(year, month)[1])
            target = _dt.date(year, month, day)
            return (f"{'Aaj se' if not back else ''} {n} mahine "
                    f"{'pehle' if back else 'baad'}: "
                    f"{target.strftime('%A, %d %B %Y')}.")
        elif re.search(r"\b(saal|year|years|varsh)\b", t):
            target = base.replace(year=base.year + sign * n)
            return (f"{n} saal {'pehle' if back else 'baad'}: "
                    f"{target.strftime('%A, %d %B %Y')}.")
        else:
            delta = _dt.timedelta(days=n)
            unit = f"{n} din"
        target = base + sign * delta
    except (ValueError, OverflowError):
        return _TOO_FAR
    return (f"{'Aaj se ' if not back else ''}{unit} "
            f"{'pehle' if back else 'baad'}: "
            f"{target.strftime('%A, %d %B %Y')}.")


# ── countdown ("diwali me kitne din bache") ──────────────────────────── #

def age_from(text: str, base: Optional[_dt.date] = None) -> Optional[str]:
    """Age in years/months/days from a spoken birthdate. Handles a bare
    year ('main 1995 me paida hua') or a full date ('15 aug 2000')."""
    base = base or _dt.date.today()
    t = (text or "").strip().lower()
    # A full date first (day+month or dd/mm/yyyy); else a bare 4-digit year.
    bd = _parse_birthdate(t, base)
    if bd is None:
        return None
    if bd > base:
        return "Wo date to future me hai, sir — birthdate check karo."
    years = base.year - bd.year - ((base.month, base.day) < (bd.month, bd.day))
    # months + days remainder
    m_anchor = _dt.date(base.year - (1 if (base.month, base.day)
                                     < (bd.month, bd.day) else 0),
                        bd.month, min(bd.day, 28))
    months = (base.year - m_anchor.year) * 12 + (base.month - m_anchor.month)
    months %= 12
    if bd.month == base.month and bd.day == base.day:
        return f"Aap {years} saal ke ho gaye — happy birthday, sir!"
    return f"Aapki age {years} saal {months} mahine hai (born {bd.strftime('%d %B %Y')})."


def _parse_birthdate(t: str, base: _dt.date) -> Optional[_dt.date]:
    # explicit full date with a year
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", t)
    if m:
        dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        yy += 2000 if yy < 100 and yy <= (base.year % 100) else (1900 if yy < 100 else 0)
        try:
            return _dt.date(yy, mm, dd)
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+([a-z]{3,9})\s+(\d{4})\b", t)
    if m and _MONTHS.get(m.group(2)):
        try:
            return _dt.date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    # bare year ("1995 me paida hua") — assume mid-year is unknown, use Jan 1
    ym = re.search(r"\b(19\d{2}|20\d{2})\b", t)
    if ym:
        yr = int(ym.group(1))
        if yr <= base.year:
            return _dt.date(yr, 1, 1)
    return None


def convert_time_zone(text: str) -> Optional[str]:
    """'3pm IST london me kitne baje' — convert a clock time from one zone
    to another. Source defaults to India when only a target is named."""
    try:
        from zoneinfo import ZoneInfo
    except Exception:
        return None
    t = (text or "").lower()
    tm = _TIME_RE.search(t)
    if not tm:
        return None
    hh = int(tm.group(1))
    mm = int(tm.group(2)) if tm.group(2) else 0
    suf = (tm.group(3) or "").lower()
    if suf == "pm" and hh < 12:
        hh += 12
    elif suf == "am" and hh == 12:
        hh = 0
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None

    # Collect place mentions in TEXT order (dict order would scramble src/dst).
    # Longer names first so "new york" wins over a stray "york"-less match.
    found = []
    for place, zone in _CITY_ZONE.items():
        m = re.search(rf"\b{re.escape(place)}\b", t)
        if m:
            found.append((m.start(), place, zone))
    found.sort()
    seen = set()
    zones = [(p, z) for _pos, p, z in found
             if not (z in seen or seen.add(z))]
    if not zones:
        return None
    src_place, src_zone = ("india", "Asia/Kolkata")
    dst = None
    if len(zones) >= 2:
        src_place, src_zone = zones[0]
        dst_place, dst_zone = zones[-1]
        dst = (dst_place, dst_zone)
    else:
        dst = zones[0]
    dst_place, dst_zone = dst
    if src_zone == dst_zone:
        return None
    today = _dt.datetime.now().date()
    src_dt = _dt.datetime(today.year, today.month, today.day, hh, mm,
                          tzinfo=ZoneInfo(src_zone))
    out = src_dt.astimezone(ZoneInfo(dst_zone))
    day_note = ""
    if out.date() > src_dt.date():
        day_note = " (agle din)"
    elif out.date() < src_dt.date():
        day_note = " (pichhle din)"
    return (f"{src_dt.strftime('%I:%M %p').lstrip('0')} {src_place.title()} = "
            f"{out.strftime('%I:%M %p').lstrip('0')} {dst_place.title()}"
            f"{day_note}.")


def day_of_week(text: str, base: Optional[_dt.date] = None) -> Optional[str]:
    """'15 august 2027 ko kaunsa din hai' → Sunday. Past dates read as
    'tha', future as 'hoga', today as 'aaj'."""
    base = base or _dt.date.today()
    d = parse_date(text, base)
    if d is None:
        # bare year alone isn't a day; need at least a day+month
        return None
    name = d.strftime("%A")
    when = d.strftime("%d %B %Y")
    if d == base:
        return f"{when} to aaj hi hai — {name}."
    tense = "tha" if d < base else "hoga"
    return f"{when} ko {name} {tense}."


_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?", re.I)


def time_until(text: str, now: Optional[_dt.datetime] = None) -> Optional[str]:
    """'5 baje tak kitna time hai' / '8 pm tak kitni der' — time remaining
    until a clock time today (rolls to tomorrow if already past)."""
    now = now or _dt.datetime.now()
    t = (text or "").lower()
    m = _TIME_RE.search(t)
    if not m or not (m.group(3) or "baje" in t or "pm" in t or "am" in t
                     or "tak" in t):
        return None
    hh = int(m.group(1))
    mm = int(m.group(2)) if m.group(2) else 0
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    suffix = (m.group(3) or "").lower()
    explicit = suffix in ("am", "pm")
    if suffix == "pm" and hh < 12:
        hh += 12
    elif suffix == "am" and hh == 12:
        hh = 0

    def _next(h: int) -> _dt.datetime:
        tgt = now.replace(hour=h % 24, minute=mm, second=0, microsecond=0)
        return tgt + _dt.timedelta(days=1) if tgt <= now else tgt

    if not explicit and hh <= 12:
        # 12-hour ambiguity: "5 baje" could be 05:00 or 17:00. Pick the
        # SOONEST future one — matches how people actually mean it.
        target = min(_next(hh), _next((hh + 12) % 24))
    else:
        target = _next(hh)
    rolled = target.date() > now.date()
    delta = target - now
    total_min = int(delta.total_seconds() // 60)
    h, mnt = divmod(total_min, 60)
    parts = []
    if h:
        parts.append(f"{h} ghante")
    parts.append(f"{mnt} minute")
    tail = " (kal)" if rolled else ""
    return (f"{target.strftime('%I:%M %p').lstrip('0')} tak "
            + " ".join(parts) + f" bache hain{tail}.")


def days_until(text: str, base: Optional[_dt.date] = None) -> Optional[str]:
    base = base or _dt.date.today()
    target = parse_date(text, base)
    if target is None:
        return None
    delta = (target - base).days
    when = target.strftime("%A, %d %B %Y")
    if delta == 0:
        return f"Wo to aaj hi hai ({when})!"
    if delta < 0:
        return f"{when} to nikal chuka — {abs(delta)} din pehle tha."
    if delta == 1:
        return f"Bas kal ({when})!"
    weeks = delta // 7
    extra = f" (~{weeks} hafte)" if weeks >= 2 else ""
    return f"{when} mein {delta} din bache hain{extra}."
