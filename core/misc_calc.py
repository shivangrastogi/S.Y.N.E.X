"""Zodiac sign from birthdate + running-pace calculator. Pure math, offline."""
from __future__ import annotations

import re
from typing import Optional

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# (sign, hemisphere emoji-free label, start-day of the sign within its month)
# each entry: month -> list of (from_day, sign) cutoffs
_ZODIAC = [
    (1, 20, "Capricorn", "Aquarius"),
    (2, 19, "Aquarius", "Pisces"),
    (3, 21, "Pisces", "Aries"),
    (4, 20, "Aries", "Taurus"),
    (5, 21, "Taurus", "Gemini"),
    (6, 21, "Gemini", "Cancer"),
    (7, 23, "Cancer", "Leo"),
    (8, 23, "Leo", "Virgo"),
    (9, 23, "Virgo", "Libra"),
    (10, 23, "Libra", "Scorpio"),
    (11, 22, "Scorpio", "Sagittarius"),
    (12, 22, "Sagittarius", "Capricorn"),
]
_TRAITS = {
    "Aries": "energetic, bold", "Taurus": "steady, reliable",
    "Gemini": "curious, chatty", "Cancer": "caring, intuitive",
    "Leo": "confident, warm", "Virgo": "practical, precise",
    "Libra": "balanced, social", "Scorpio": "intense, focused",
    "Sagittarius": "adventurous, open", "Capricorn": "disciplined, driven",
    "Aquarius": "inventive, independent", "Pisces": "gentle, imaginative",
}


def _sign(month: int, day: int) -> str:
    _, cut, before, after = _ZODIAC[month - 1]
    return before if day < cut else after


def zodiac_sign(text: str) -> Optional[str]:
    t = (text or "").lower()
    month = None
    for name, num in _MONTHS.items():
        if re.search(rf"\b{name}\b", t):
            month = num
            break
    day = None
    if month is not None:
        dm = re.search(r"\b(\d{1,2})\b", t)
        day = int(dm.group(1)) if dm else None
    else:
        # numeric date: dd/mm or dd-mm  (day first, Indian convention)
        nm = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})\b", t)
        if nm:
            day, month = int(nm.group(1)), int(nm.group(2))
    if not month or not day or not (1 <= month <= 12) or not (1 <= day <= 31):
        return ("Janamdin batao — jaise '15 august' ya '15/08' — "
                "main zodiac sign bata dunga.")
    sign = _sign(month, day)
    return f"Zodiac sign: {sign} ({_TRAITS[sign]})."


def _parse_time_secs(text: str) -> Optional[float]:
    # explicit clock form hh:mm:ss or mm:ss
    cm = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", text)
    if cm:
        a, b, c = cm.group(1), cm.group(2), cm.group(3)
        if c is not None:
            return int(a) * 3600 + int(b) * 60 + int(c)
        return int(a) * 60 + int(b)
    secs = 0.0
    hit = False
    hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hour|ghante|ghanta)", text)
    if hm:
        secs += float(hm.group(1)) * 3600; hit = True
    mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|minute|mins|minit)", text)
    if mm:
        secs += float(mm.group(1)) * 60; hit = True
    sm = re.search(r"(\d+(?:\.\d+)?)\s*(?:sec|second|s\b)", text)
    if sm:
        secs += float(sm.group(1)); hit = True
    return secs if hit else None


def _fmt_pace(secs_per_km: float) -> str:
    m, s = divmod(round(secs_per_km), 60)
    return f"{m}:{s:02d}"


def running_pace(text: str) -> Optional[str]:
    t = (text or "").lower()
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(k|km|kilomet|mile)", t)
    if not dm:
        return ("Distance aur time dono do — jaise '5 km 25 min' — "
                "main pace nikaal dunga.")
    dist = float(dm.group(1))
    if dm.group(2).startswith("mile"):
        dist *= 1.609344
    # strip the distance number so time parsing doesn't grab it
    rest = t[:dm.start()] + t[dm.end():]
    secs = _parse_time_secs(rest)
    if secs is None or dist <= 0 or secs <= 0:
        return ("Time bhi do — jaise '5 km 25 min' ya '5 km 25:30'.")
    pace = secs / dist
    speed = dist / (secs / 3600)
    return (f"{_fmt(dist)} km in {_fmt_clock(secs)}: pace {_fmt_pace(pace)} /km, "
            f"speed {speed:.1f} km/h.")


def _fmt(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.2f}"


def _fmt_clock(secs: float) -> str:
    secs = round(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fuel_trip_cost(text: str) -> Optional[str]:
    """distance(km) + mileage(km/l) + fuel price(/l) -> litres & cost.
    '500 km 15 kmpl 100 rupee petrol'."""
    t = (text or "").lower()
    spans = []

    def _grab(pat):
        m = re.search(pat, t)
        if m:
            spans.append((m.start(), m.end()))
            return float(m.group(1))
        return None

    mileage = _grab(r"(\d+(?:\.\d+)?)\s*(?:kmpl|km ?/ ?l|km per (?:litre|liter|l)|kilometre per litre)")
    if mileage is None:
        mileage = _grab(r"mileage\s*(?:of\s*)?(\d+(?:\.\d+)?)")
    price = _grab(r"(\d+(?:\.\d+)?)\s*(?:rupee|rupees|rs|₹|/l|per litre|per liter)")
    if price is None:
        price = _grab(r"(?:petrol|diesel|fuel|price)\s*(\d+(?:\.\d+)?)")
    # distance = a 'km' number that isn't the mileage span
    dist = None
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet)", t):
        if any(s <= m.start() < e for s, e in spans):
            continue
        dist = float(m.group(1))
        break
    if not dist or not mileage or mileage <= 0:
        return ("Distance, mileage aur fuel price do — jaise "
                "'500 km 15 kmpl 100 rupee'.")
    litres = dist / mileage
    if price is None:
        return (f"{_fmt(dist)} km @ {_fmt(mileage)} km/l = {_fmt(litres)} litre "
                "chahiye. Fuel price bhi do to cost bhi bata dunga.")
    cost = litres * price
    return (f"{_fmt(dist)} km @ {_fmt(mileage)} km/l = {_fmt(litres)} litre "
            f"@ {_fmt(price)}/l = {_fmt(cost)} total.")


def water_intake(text: str) -> Optional[str]:
    """~35 ml per kg body weight per day (+ activity bump)."""
    t = (text or "").lower()
    wm = re.search(r"\b(?:weight|wt|vajan|wajan|vazan)\b\s*(\d+(?:\.\d+)?)", t)
    weight = float(wm.group(1)) if wm else None
    if weight is None:
        for f in re.findall(r"\d+(?:\.\d+)?", t):
            v = float(f)
            if 25 <= v <= 250:
                weight = v
                break
    if not weight:
        return ("Apna weight batao — jaise 'weight 70 water intake' — "
                "main daily paani ki zaroorat bata dunga.")
    base = weight * 0.035  # litres
    active = re.search(r"\b(active|exercise|gym|workout|run|sports?|khel)", t)
    note = ""
    if active:
        base += 0.5
        note = " (exercise ke liye +0.5 L jodha)"
    glasses = round(base * 1000 / 250)
    return (f"~{base:.1f} litre/day paani piyo ({glasses} glasses of 250ml){note}. "
            "Garmi/exercise me thoda zyada. (General guide, medical advice nahi.)")


_LIFE_PATH = {
    1: "leader, independent", 2: "diplomat, sensitive",
    3: "creative, expressive", 4: "practical, disciplined",
    5: "adventurous, free", 6: "nurturing, responsible",
    7: "analytical, spiritual", 8: "ambitious, material",
    9: "compassionate, idealistic", 11: "intuitive, inspired (master)",
    22: "master builder (master)", 33: "master teacher (master)",
}


def _reduce(n: int) -> int:
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n


def numerology(text: str) -> Optional[str]:
    """Life-path number from a birthdate (dd mm yyyy in any separator)."""
    t = (text or "").lower()
    # need day, month, year. Accept dd/mm/yyyy, or day + month-name + year.
    dm = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b", t)
    if dm:
        day, month, year = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
    else:
        month = None
        for name, num in _MONTHS.items():
            if re.search(rf"\b{name}\b", t):
                month = num
                break
        ym = re.search(r"\b(\d{4})\b", t)
        dd = re.search(r"\b(\d{1,2})\b", t)
        if month is None or ym is None or dd is None:
            return ("Poori janam-tareekh do — jaise '15/08/1998' — "
                    "main life-path number nikaal dunga.")
        day, year = int(dd.group(1)), int(ym.group(1))
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 9999):
        return "Tareekh sahi nahi lag rahi — jaise '15/08/1998' do."
    total = sum(int(d) for d in f"{day:02d}{month:02d}{year}")
    lp = _reduce(total)
    trait = _LIFE_PATH.get(lp, "")
    return (f"Life-path number: {lp}" + (f" ({trait})." if trait else ".") +
            " (Numerology fun hai, science nahi.)")


def heat_index(text: str) -> Optional[str]:
    """'Feels like' temp from air temp (C) + relative humidity (%).
    NWS Rothfusz regression (computed in F, reported in C)."""
    t = (text or "").lower()
    tm = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°?\s*c\b|degree|degrees|celsius)", t)
    if not tm:
        tm = re.search(r"temp\w*\s*(?:is|hai|of|=|:)?\s*(-?\d+(?:\.\d+)?)", t)
    # humidity: prefer the %-tagged number, then 'humidity N', then 'N humidity'
    hm = re.search(r"(\d+(?:\.\d+)?)\s*%", t) \
        or re.search(r"(?:humidity|nami|humid)\s*(?:is|hai|of|=|:)?\s*(\d+(?:\.\d+)?)", t) \
        or re.search(r"(\d+(?:\.\d+)?)\s*(?:percent|humidity|nami)", t)
    if not tm or not hm:
        return ("Temperature aur humidity dono do — jaise "
                "'35 degree 60% humidity' — feels-like bata dunga.")
    tc = float(tm.group(1))
    rh = max(0.0, min(float(hm.group(1)), 100.0))
    tf = tc * 9 / 5 + 32
    if tf < 80:                      # formula only valid in the warm range
        return (f"{_fmt(tc)}°C @ {_fmt(rh)}% humidity: feels about the same "
                f"(~{_fmt(tc)}°C). Heat index tabhi matter karta hai jab garmi ho.")
    hi = (-42.379 + 2.04901523 * tf + 10.14333127 * rh
          - 0.22475541 * tf * rh - 0.00683783 * tf * tf
          - 0.05481717 * rh * rh + 0.00122874 * tf * tf * rh
          + 0.00085282 * tf * rh * rh - 0.00000199 * tf * tf * rh * rh)
    hi_c = (hi - 32) * 5 / 9
    if hi_c >= 54:
        band = "EXTREME DANGER — heat stroke risk"
    elif hi_c >= 41:
        band = "danger — heavy exertion se bacho"
    elif hi_c >= 32:
        band = "extreme caution — cramps/exhaustion possible"
    else:
        band = "caution — thoda thaka sakta hai"
    return (f"{_fmt(tc)}°C @ {_fmt(rh)}% humidity feels like ~{hi_c:.1f}°C "
            f"({band}). Paani peete raho.")


def _time_hours(text: str) -> Optional[float]:
    """Total time in hours from 'X hr Y min' style phrases."""
    hrs = 0.0
    hit = False
    hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h\b|ghante|ghanta)", text)
    if hm:
        hrs += float(hm.group(1)); hit = True
    mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|minit)", text)
    if mm:
        hrs += float(mm.group(1)) / 60; hit = True
    return hrs if hit else None


def travel_time(text: str) -> Optional[str]:
    """Solve distance = speed x time when any two are given."""
    t = (text or "").lower()
    sm = re.search(r"(\d+(?:\.\d+)?)\s*(?:kmph|km ?/ ?h|km per h(?:our|r)?|"
                   r"kilometre per hour)", t)
    speed = float(sm.group(1)) if sm else None
    # distance = a 'km' number that isn't the speed span
    dist = None
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet)", t):
        if sm and sm.start() <= m.start() < sm.end():
            continue
        dist = float(m.group(1))
        break
    hours = _time_hours(t)
    known = sum(x is not None for x in (speed, dist, hours))
    if known < 2:
        return ("Do cheezein do (distance / speed / time) — jaise "
                "'120 km 60 kmph kitni der' — main teesri nikaal dunga.")
    if dist is not None and speed and hours is None:
        h = dist / speed
        return f"{_fmt(dist)} km @ {_fmt(speed)} km/h = {_fmt_hm(h)} lagenge."
    if dist is not None and hours and speed is None:
        s = dist / hours
        return f"{_fmt(dist)} km in {_fmt_hm(hours)} = {s:.1f} km/h speed."
    if speed and hours and dist is None:
        d = speed * hours
        return f"{_fmt(speed)} km/h x {_fmt_hm(hours)} = {_fmt(d)} km cover."
    # all three given -> just restate
    return f"{_fmt(dist)} km, {_fmt(speed)} km/h, {_fmt_hm(hours)}."


def _fmt_hm(hours: float) -> str:
    total_min = round(hours * 60)
    h, m = divmod(total_min, 60)
    if h and m:
        return f"{h} hr {m} min"
    if h:
        return f"{h} hr"
    return f"{m} min"


def area_calc(text: str) -> Optional[str]:
    """Room/plot area + perimeter from L x W. '10 by 12 feet'."""
    t = (text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|by|\*|into|×)\s*(\d+(?:\.\d+)?)", t)
    if not m:
        return ("Do dimensions do — jaise '10 by 12 feet' — main area aur "
                "perimeter nikaal dunga.")
    a, b = float(m.group(1)), float(m.group(2))
    if a <= 0 or b <= 0:
        return "Dimensions positive honi chahiye."
    metre = bool(re.search(r"\b(met(er|re)s?|\bm\b|meter)\b", t))
    area = a * b
    perim = 2 * (a + b)
    if metre:
        return (f"{_fmt(a)}m x {_fmt(b)}m = {_fmt(area)} sq.m area, "
                f"{_fmt(perim)}m perimeter ({_fmt(area * 10.7639)} sq.ft).")
    return (f"{_fmt(a)}ft x {_fmt(b)}ft = {_fmt(area)} sq.ft area, "
            f"{_fmt(perim)}ft perimeter ({_fmt(area * 0.092903)} sq.m).")


def wind_chill(text: str) -> Optional[str]:
    """'Feels like' cold from air temp (C) + wind speed (km/h).
    Environment Canada formula; valid for T<=10C and wind>=5 km/h."""
    t = (text or "").lower()
    tm = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°?\s*c\b|degree|degrees|celsius)", t)
    if not tm:
        tm = re.search(r"temp\w*\s*(?:is|hai|of|=|:)?\s*(-?\d+(?:\.\d+)?)", t)
    wm = re.search(r"(\d+(?:\.\d+)?)\s*(?:kmph|km ?/ ?h|km per h|wind|hawa)", t)
    if not wm:
        wm = re.search(r"(?:wind|hawa)\s*(?:speed)?\s*(\d+(?:\.\d+)?)", t)
    if not tm or not wm:
        return ("Temperature aur wind speed do — jaise '5 degree 30 kmph wind' "
                "— feels-like cold bata dunga.")
    tc = float(tm.group(1))
    v = float(wm.group(1))
    if tc > 10 or v < 5:
        return (f"{_fmt(tc)}°C @ {_fmt(v)} km/h wind: wind chill sirf thand "
                "(<=10°C) aur tez hawa (>=5 km/h) me matter karta hai.")
    v16 = v ** 0.16
    wc = 13.12 + 0.6215 * tc - 11.37 * v16 + 0.3965 * tc * v16
    if wc <= -28:
        band = "frostbite risk — bahar mat ruko"
    elif wc <= -10:
        band = "kaafi thand — gloves/cap zaroor"
    else:
        band = "thand lagegi — jacket pehno"
    return (f"{_fmt(tc)}°C @ {_fmt(v)} km/h wind feels like ~{wc:.1f}°C "
            f"({band}).")


def dew_point(text: str) -> Optional[str]:
    """Dew point from air temp (C) + relative humidity (%). Magnus formula."""
    import math
    t = (text or "").lower()
    tm = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°?\s*c\b|degree|degrees|celsius)", t)
    if not tm:
        tm = re.search(r"temp\w*\s*(?:is|hai|of|=|:)?\s*(-?\d+(?:\.\d+)?)", t)
    hm = re.search(r"(\d+(?:\.\d+)?)\s*%", t) \
        or re.search(r"(?:humidity|nami|humid)\s*(?:is|hai|of|=|:)?\s*(\d+(?:\.\d+)?)", t) \
        or re.search(r"(\d+(?:\.\d+)?)\s*(?:percent|humidity|nami)", t)
    if not tm or not hm:
        return ("Temperature aur humidity do — jaise '30 degree 70% humidity' "
                "— dew point bata dunga.")
    tc = float(tm.group(1))
    rh = float(hm.group(1))
    if not (0 < rh <= 100):
        return "Humidity 1-100% ke beech do."
    a, b = 17.62, 243.12
    gamma = math.log(rh / 100.0) + a * tc / (b + tc)
    td = (b * gamma) / (a - gamma)
    if td >= 24:
        comfort = "chipchipa/uncomfortable"
    elif td >= 18:
        comfort = "humid feel"
    elif td >= 10:
        comfort = "comfortable"
    else:
        comfort = "dry/pleasant"
    return (f"{_fmt(tc)}°C @ {_fmt(rh)}% humidity: dew point ~{td:.1f}°C "
            f"({comfort}).")


_SIZE_MB = {"kb": 0.001, "mb": 1.0, "gb": 1000.0, "tb": 1_000_000.0}


def download_time(text: str) -> Optional[str]:
    """Time to download a file: size / bandwidth. Speed treated as Mbps (bits)."""
    t = (text or "").lower()
    sm = re.search(r"(\d+(?:\.\d+)?)\s*(gb|mb|kb|tb)\b", t)
    spd = re.search(r"(\d+(?:\.\d+)?)\s*(?:mbps|mb ?/ ?s|megabit|mbit)", t)
    if not sm or not spd:
        return ("File size aur speed do — jaise '2 GB 20 mbps' — main "
                "download time bata dunga.")
    size_mb = float(sm.group(1)) * _SIZE_MB[sm.group(2)]
    mbps = float(spd.group(1))
    if mbps <= 0:
        return "Speed positive honi chahiye."
    secs = size_mb * 8 / mbps          # MB -> megabits / Mbps
    return (f"{sm.group(1)}{sm.group(2).upper()} @ {_fmt(mbps)} Mbps = "
            f"{_fmt_dur(secs)} (theoretical; real speed kam ho sakti hai).")


def _fmt_dur(secs: float) -> str:
    secs = round(secs)
    if secs < 60:
        return f"{secs} sec"
    if secs < 3600:
        m, s = divmod(secs, 60)
        return f"{m} min {s} sec" if s else f"{m} min"
    h, rem = divmod(secs, 3600)
    m = rem // 60
    return f"{h} hr {m} min" if m else f"{h} hr"


def paint_quantity(text: str) -> Optional[str]:
    """Litres of paint for a wall area. ~110 sqft/litre/coat, 2 coats default."""
    t = (text or "").lower()
    dim = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|by|\*|into|×)\s*(\d+(?:\.\d+)?)", t)
    am = re.search(r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*(?:ft|feet)|sqft|square feet)", t)
    if am:
        area = float(am.group(1))
    elif dim:
        area = float(dim.group(1)) * float(dim.group(2))
    else:
        return ("Wall ka area ya dimensions do — jaise '500 sqft' ya "
                "'10 by 12 feet' — main paint quantity bata dunga.")
    if area <= 0:
        return "Area positive hona chahiye."
    cm = re.search(r"(\d+)\s*coat", t)
    coats = int(cm.group(1)) if cm else 2
    coats = max(1, min(coats, 5))
    coverage = 110.0                    # sqft per litre per coat
    litres = area / coverage * coats
    return (f"{_fmt(area)} sq.ft, {coats} coat = ~{litres:.1f} litre paint "
            f"(~{coverage:.0f} sqft/litre/coat). Thoda extra rakhna.")


def tile_count(text: str) -> Optional[str]:
    """Tiles needed for a floor: floor area / tile area + 10% wastage.
    '200 sqft floor 2x2 feet tiles'."""
    t = (text or "").lower()
    am = re.search(r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*(?:ft|feet)|sqft|square feet)", t)
    if not am:
        return ("Floor area (sqft) aur tile size do — jaise "
                "'200 sqft 2x2 feet tiles'.")
    floor = float(am.group(1))
    # tile dimensions near the word 'tile' (or any AxB with a unit)
    tm = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|by|\*|×)\s*(\d+(?:\.\d+)?)\s*"
                   r"(feet|ft|inch|in|mm|cm)?", t)
    if not tm:
        return ("Tile ka size batao — jaise '2x2 feet' ya '12x12 inch' ya "
                "'600x600 mm'.")
    a, b = float(tm.group(1)), float(tm.group(2))
    unit = tm.group(3) or "feet"
    to_ft = {"feet": 1.0, "ft": 1.0, "inch": 1 / 12, "in": 1 / 12,
             "mm": 1 / 304.8, "cm": 1 / 30.48}[unit]
    tile_ft2 = (a * to_ft) * (b * to_ft)
    if tile_ft2 <= 0:
        return "Tile size sahi nahi lag raha."
    import math
    base = math.ceil(floor / tile_ft2)
    with_waste = (base * 11 + 9) // 10      # +10% wastage, integer ceil
    return (f"{_fmt(floor)} sq.ft floor, {_fmt(a)}x{_fmt(b)} {unit} tiles "
            f"({_fmt(tile_ft2)} sq.ft each): ~{base} tiles, "
            f"{with_waste} with 10% wastage.")


def recipe_scale(text: str) -> Optional[str]:
    """Scale a recipe by serving ratio. '4 log ki recipe 6 ke liye'."""
    t = (text or "").lower()
    factor = None
    if re.search(r"\b(double|dugna|do\s*guna|twice)\b", t):
        factor = 2.0
    elif re.search(r"\b(triple|teen\s*guna)\b", t):
        factor = 3.0
    elif re.search(r"\b(half|aadha|adha)\b", t):
        factor = 0.5
    frm = re.search(r"(\d+(?:\.\d+)?)\s*(?:log|serving|servings|people|"
                    r"person|portions?|plate)", t)
    to = re.search(r"(?:to|se|for|ke liye|banao)\s*(\d+(?:\.\d+)?)", t)
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if factor is None and frm and to:
        a, b = float(frm.group(1)), float(to.group(1))
        if a > 0:
            factor = b / a
    elif factor is None and len(nums) >= 2:
        a, b = float(nums[0]), float(nums[1])
        if a > 0:
            factor = b / a
    if not factor or factor <= 0:
        return ("Original aur target servings do — jaise '4 log ki recipe "
                "6 ke liye' — main scale factor bata dunga.")
    pct = f"{factor:g}x"
    return (f"Recipe ko {pct} karo — har ingredient ki quantity {factor:g} se "
            "multiply karo (cooking time same rakhna).")


def ppi_calculator(text: str) -> Optional[str]:
    """Pixel density: sqrt(w^2+h^2)/diagonal_inches. '1920x1080 15.6 inch'."""
    import math
    t = (text or "").lower()
    rm = re.search(r"(\d{3,5})\s*(?:x|by|\*|×)\s*(\d{3,5})", t)
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:inch|inches|in|\"|diagonal)", t)
    if not rm or not dm:
        return ("Resolution aur screen size do — jaise '1920x1080 15.6 inch' "
                "— main PPI (pixel density) bata dunga.")
    w, h = int(rm.group(1)), int(rm.group(2))
    diag = float(dm.group(1))
    if diag <= 0:
        return "Screen size positive honi chahiye."
    ppi = math.hypot(w, h) / diag
    sharp = ("retina-class (bahut sharp)" if ppi >= 300 else
             "sharp" if ppi >= 200 else
             "theek-thaak" if ppi >= 130 else "kam density")
    return (f"{w}x{h} on {_fmt(diag)}\" = ~{ppi:.0f} PPI ({sharp}).")


_SOUND_MPS = 343.0     # speed of sound ~20°C


def thunder_distance(text: str) -> Optional[str]:
    """Distance to lightning from the flash-to-thunder gap (~343 m/s)."""
    t = (text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|second|\bs\b)", t)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)", t)
    if not m:
        return ("Kitne second ka gap tha bijli aur gadgadahat me? Jaise "
                "'5 second baad thunder' — main distance bata dunga.")
    secs = float(m.group(1))
    if secs <= 0:
        return "Gap positive hona chahiye."
    metres = secs * _SOUND_MPS
    km = metres / 1000
    miles = metres / 1609.344
    return (f"{_fmt(secs)} sec gap = lightning ~{km:.2f} km ({miles:.2f} miles) "
            "door thi. (Sound ~343 m/s.)")


def ohms_law(text: str) -> Optional[str]:
    """V = I x R. Give any two, get the third + power. '5 volt 2 amp'."""
    t = (text or "").lower()
    vm = re.search(r"(\d+(?:\.\d+)?)\s*(?:volts?|v\b)", t)
    im = re.search(r"(\d+(?:\.\d+)?)\s*(m?a\b|amps?|ampere|milliamp)", t)
    rm = re.search(r"(\d+(?:\.\d+)?)\s*(?:ohms?|ohm|resistance|Ω)", t)
    V = float(vm.group(1)) if vm else None
    I = None
    if im:
        I = float(im.group(1))
        if im.group(1) and (im.group(2) or "").startswith("m"):
            I /= 1000.0
    R = float(rm.group(1)) if rm else None
    known = sum(x is not None for x in (V, I, R))
    if known < 2:
        return ("Do values do (volt / amp / ohm) — jaise '5 volt 10 ohm' — "
                "main teesra + power nikaal dunga.")
    if V is not None and I is not None and R is None:
        if I == 0:
            return "Current zero nahi ho sakta."
        R = V / I
        third = f"Resistance = {_fmt(R)} ohm"
    elif V is not None and R is not None and I is None:
        if R == 0:
            return "Resistance zero nahi ho sakta."
        I = V / R
        third = f"Current = {_fmt(I)} A"
    elif I is not None and R is not None and V is None:
        V = I * R
        third = f"Voltage = {_fmt(V)} V"
    else:
        third = "(sab pata hai)"
    power = V * I
    return (f"{third}. (V={_fmt(V)}V, I={_fmt(I)}A, R={_fmt(R)}ohm, "
            f"Power={_fmt(power)}W.)")


def battery_life(text: str) -> Optional[str]:
    """Runtime = capacity(mAh) / draw(mA). '3000 mAh 500 mA'."""
    t = (text or "").lower()
    cm = re.search(r"(\d+(?:\.\d+)?)\s*mah", t)
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:ma\b|milliamp|draw)", t)
    cap = float(cm.group(1)) if cm else None
    # draw = a 'mA' number that isn't the capacity
    draw = None
    if dm and (not cm or dm.start() != cm.start()):
        draw = float(dm.group(1))
    if cap is None or draw is None or draw <= 0:
        return ("Battery capacity (mAh) aur draw (mA) do — jaise "
                "'3000 mAh 500 mA' — main runtime bata dunga.")
    hours = cap / draw
    real = hours * 0.85       # real-world efficiency
    h, m = divmod(round(hours * 60), 60)
    ideal = f"{h} hr {m} min" if m else f"{h} hr"
    return (f"{_fmt(cap)} mAh @ {_fmt(draw)} mA = ~{ideal} (ideal). "
            f"Real-world ~{real:.1f} hr (efficiency ke saath).")


_C_LIGHT = 299_792_458.0        # m/s


def _fmt_si(value: float, unit: str) -> str:
    """Human SI scaling for a base-unit value."""
    if unit == "hz":
        for div, suf in ((1e12, "THz"), (1e9, "GHz"), (1e6, "MHz"),
                         (1e3, "kHz"), (1, "Hz")):
            if value >= div:
                return f"{value/div:.3g} {suf}"
        return f"{value:.3g} Hz"
    # metres
    for div, suf in ((1000, "km"), (1, "m"), (1e-2, "cm"), (1e-3, "mm"),
                     (1e-6, "µm"), (1e-9, "nm")):
        if value >= div:
            return f"{value/div:.3g} {suf}"
    return f"{value:.3g} m"


def frequency_wavelength(text: str) -> Optional[str]:
    """EM frequency <-> wavelength (c = f x lambda)."""
    t = (text or "").lower()
    fm = re.search(r"(\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)\b", t)
    wm = re.search(r"(\d+(?:\.\d+)?)\s*(nm|µm|um|mm|cm|km|m|meter|metre)\b", t)
    if fm:
        disp = {"hz": "Hz", "khz": "kHz", "mhz": "MHz", "ghz": "GHz"}
        mult = {"hz": 1, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}[fm.group(2)]
        freq = float(fm.group(1)) * mult
        if freq <= 0:
            return "Frequency positive honi chahiye."
        wl = _C_LIGHT / freq
        return (f"{fm.group(1)} {disp[fm.group(2)]} frequency ka wavelength "
                f"= {_fmt_si(wl, 'm')} (vacuum me).")
    if wm:
        mult = {"nm": 1e-9, "µm": 1e-6, "um": 1e-6, "mm": 1e-3, "cm": 1e-2,
                "km": 1e3, "m": 1, "meter": 1, "metre": 1}[wm.group(2)]
        wl = float(wm.group(1)) * mult
        if wl <= 0:
            return "Wavelength positive honi chahiye."
        freq = _C_LIGHT / wl
        return (f"{wm.group(1)} {wm.group(2)} wavelength ki frequency "
                f"= {_fmt_si(freq, 'hz')} (vacuum me).")
    return ("Frequency ya wavelength do — jaise '100 MHz wavelength' ya "
            "'3 m wavelength ki frequency'.")


def led_resistor(text: str) -> Optional[str]:
    """Series resistor for an LED: R = (Vsupply - Vforward) / I_led."""
    t = (text or "").lower()
    fm = re.search(r"(\d+(?:\.\d+)?)\s*(?:v\b|volt)\s*(?:led|forward)|"
                   r"(?:led|forward)\s*(?:voltage|drop)?\s*(\d+(?:\.\d+)?)\s*(?:v\b|volt)?", t)
    im = re.search(r"(\d+(?:\.\d+)?)\s*(m?a\b|milliamp)", t)
    volts = re.findall(r"(\d+(?:\.\d+)?)\s*(?:v\b|volt)", t)
    if not im or len(volts) < 2:
        return ("Supply voltage, LED voltage aur current do — jaise "
                "'5V supply 2V LED 20mA' — main resistor bata dunga.")
    vf = None
    if fm:
        vf = float(fm.group(1) or fm.group(2))
    vs_list = [float(v) for v in volts]
    if vf is None:
        vf = min(vs_list)
        vs = max(vs_list)
    else:
        others = [v for v in vs_list if abs(v - vf) > 1e-9] or vs_list
        vs = max(others)
    cur = float(im.group(1))
    if (im.group(2) or "").startswith("m"):
        cur /= 1000.0
    if cur <= 0:
        return "Current positive honi chahiye."
    if vs <= vf:
        return "Supply voltage LED voltage se zyada honi chahiye."
    r = (vs - vf) / cur
    power = (vs - vf) * cur
    return (f"LED resistor: ({_fmt(vs)}V - {_fmt(vf)}V) / {_fmt(cur*1000)}mA = "
            f"{_fmt(r)} ohm (nearest standard: {_nearest_e12(r)} ohm). "
            f"Resistor power ~{_fmt(power*1000)} mW.")


_E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]


def _nearest_e12(r: float) -> str:
    if r <= 0:
        return "0"
    best, bestd = None, None
    for mult in (0.1, 1, 10, 100, 1000, 10000, 100000):
        for base in _E12:
            val = base * mult
            d = abs(val - r)
            if bestd is None or d < bestd:
                best, bestd = val, d
    return str(int(best)) if best == int(best) else f"{best:g}"


# Beaufort scale cutoffs (upper km/h bound, number, name)
_BEAUFORT = [
    (1, 0, "Calm"), (5, 1, "Light air"), (11, 2, "Light breeze"),
    (19, 3, "Gentle breeze"), (28, 4, "Moderate breeze"),
    (38, 5, "Fresh breeze"), (49, 6, "Strong breeze"), (61, 7, "Near gale"),
    (74, 8, "Gale"), (88, 9, "Strong gale"), (102, 10, "Storm"),
    (117, 11, "Violent storm"), (float("inf"), 12, "Hurricane"),
]


def beaufort_scale(text: str) -> Optional[str]:
    """Wind speed -> Beaufort number + description. Accepts km/h, mph, knots, m/s."""
    t = (text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kmph|km ?/ ?h|km|mph|knots?|kt|m ?/ ?s|mps)?", t)
    if not m:
        return ("Wind speed do — jaise '45 kmph' ya '20 knots' — main "
                "Beaufort scale bata dunga.")
    val = float(m.group(1))
    unit = (m.group(2) or "kmph").replace(" ", "")
    to_kmph = {"kmph": 1, "km/h": 1, "km": 1, "mph": 1.609344,
               "knot": 1.852, "knots": 1.852, "kt": 1.852,
               "m/s": 3.6, "mps": 3.6}.get(unit, 1)
    kmph = val * to_kmph
    for hi, num, name in _BEAUFORT:
        if kmph <= hi:
            return (f"{_fmt(val)} {unit} (~{_fmt(kmph)} km/h) = Beaufort {num} "
                    f"({name}).")
    return f"{_fmt(kmph)} km/h = Beaufort 12 (Hurricane)."


# CPCB (India) AQI bands: (upper, label, advice)
_AQI = [
    (50, "Good", "saaf hawa, koi risk nahi"),
    (100, "Satisfactory", "sensitive logon ko halki dikkat ho sakti hai"),
    (200, "Moderate", "saans ke mareezon ko halki takleef"),
    (300, "Poor", "logon ko saans lene me dikkat, mask pehno"),
    (400, "Very Poor", "lambe exposure se bimari, bahar kam niklo"),
    (500, "Severe", "sabke liye khatarnak, ghar me raho"),
]


def aqi_category(text: str) -> Optional[str]:
    """AQI number -> CPCB category + health advice."""
    m = re.search(r"\b(\d{1,4})\b", text or "")
    if not m:
        return ("AQI number batao — jaise 'AQI 180' — main category aur "
                "health advice bata dunga.")
    aqi = int(m.group(1))
    if aqi < 0:
        return "AQI negative nahi hota."
    for hi, label, advice in _AQI:
        if aqi <= hi:
            return f"AQI {aqi} = {label} ({advice})."
    return f"AQI {aqi} = Severe+ (bahut hi khatarnak, bilkul bahar mat niklo)."


_DB = [
    (30, "bahut shaant", "whisper / rustling leaves"),
    (50, "shaant", "normal ghar, fridge hum"),
    (70, "moderate", "normal conversation, AC"),
    (85, "loud", "heavy traffic; 8 ghante se zyada nuksaan"),
    (100, "bahut loud", "bike, blender; ~15 min me risk"),
    (120, "extremely loud", "concert, siren; minutes me damage"),
    (200, "painful", "jet takeoff paas se; turant damage"),
]


def decibel_scale(text: str) -> Optional[str]:
    """dB level -> loudness category + safe-exposure note."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:db|decibel|decibels)?", text or "")
    if not m or "db" not in (text or "").lower() and "decibel" not in (text or "").lower():
        m2 = re.search(r"(\d+(?:\.\d+)?)", text or "")
        if not m2:
            return ("dB level batao — jaise '85 dB' — main loudness aur "
                    "hearing risk bata dunga.")
        m = m2
    db = float(m.group(1))
    if db < 0:
        return "dB negative bahut hi rare hota hai — positive value do."
    if db > 300:
        return f"{_fmt(db)} dB real duniya me possible nahi — 0-194 dB range hoti hai."
    label, example = _DB[-1][1], _DB[-1][2]
    for hi, lb, ex in _DB:
        if db <= hi:
            label, example = lb, ex
            break
    safe = ""
    if db >= 85:
        # NIOSH: 85 dB = 8h, halve every 3 dB
        hours = 8 / (2 ** ((db - 85) / 3))
        if hours >= 1:
            safe = f" Safe exposure ~{hours:.1f} hr/day."
        elif hours * 60 >= 1:
            safe = f" Safe exposure ~{hours*60:.0f} min/day."
        else:
            safe = " Safe exposure kuch seconds — ear protection zaroori."
    return f"{_fmt(db)} dB = {label} ({example}).{safe}"


def richter_scale(text: str) -> Optional[str]:
    """Earthquake magnitude -> severity description."""
    m = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not m:
        return ("Magnitude batao — jaise 'richter 6.5' — main severity bata "
                "dunga.")
    mag = float(m.group(1))
    if mag < 0 or mag > 12:
        return "Magnitude 0-12 ke beech hoti hai."
    if mag < 2:
        sev = "micro — mehsoos nahi hota"
    elif mag < 4:
        sev = "minor — halka mehsoos, nuksaan nahi"
    elif mag < 5:
        sev = "light — mehsoos hota hai, halka nuksaan"
    elif mag < 6:
        sev = "moderate — kamzor buildings ko nuksaan"
    elif mag < 7:
        sev = "strong — bhari nuksaan aabaadi walo me"
    elif mag < 8:
        sev = "major — gambhir vinaash bade ilaake me"
    else:
        sev = "great — bhayanak tabaahi, hazaaron km tak"
    return (f"Magnitude {_fmt(mag)} = {sev}. (Har 1 point = ~32x zyada energy.)")


_UV = [
    (2, "Low", "koi khaas protection ki zaroorat nahi"),
    (5, "Moderate", "SPF 30 lagao, dopahar me chhaya me raho"),
    (7, "High", "SPF 30+, topi/sunglasses, 10am-4pm bacho"),
    (10, "Very High", "SPF 50, extra care, jalne ka risk"),
    (100, "Extreme", "bahar mat niklo dopahar me, full protection"),
]


def uv_index(text: str) -> Optional[str]:
    """UV index number -> category + sun-protection advice."""
    m = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not m:
        return ("UV index number batao — jaise 'UV 8' — main category aur "
                "protection bata dunga.")
    uv = float(m.group(1))
    if uv < 0:
        return "UV index negative nahi hota."
    for hi, label, advice in _UV:
        if uv <= hi:
            return f"UV index {_fmt(uv)} = {label} ({advice})."
    return f"UV index {_fmt(uv)} = Extreme (bahut khatarnak, full protection)."


def average_speed(text: str) -> Optional[str]:
    """Average speed over two equal-distance legs = harmonic mean 2ab/(a+b).
    (The classic 'go at 60, return at 40' problem — NOT the simple average.)"""
    t = (text or "").lower()
    speeds = [float(x) for x in re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:kmph|km ?/ ?h|km per h|mph|kmh)?", t) if x]
    speeds = [s for s in speeds if s > 0][:2]
    if len(speeds) < 2:
        return ("Do speeds do (jaate waqt aur aate waqt) — jaise "
                "'60 kmph gaye 40 kmph aaye' — main average speed bata dunga.")
    a, b = speeds[0], speeds[1]
    harm = 2 * a * b / (a + b)
    simple = (a + b) / 2
    return (f"Same distance {_fmt(a)} aur {_fmt(b)} km/h pe: average speed "
            f"{harm:.2f} km/h (harmonic mean, NOT simple {_fmt(simple)}).")


def work_rate(text: str) -> Optional[str]:
    """Time to finish a job together. 'A in 6 hrs, B in 4 hrs' -> 2.4 hrs."""
    t = (text or "").lower()
    times = [float(x) for x in re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|ghante|days?|din|minutes?|mins?)", t)]
    if len(times) < 2:
        times = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    times = [x for x in times if x > 0][:3]
    if len(times) < 2:
        return ("Do (ya zyada) times do — jaise 'A 6 ghante B 4 ghante' — "
                "main saath me kitna time lagega bata dunga.")
    rate = sum(1 / x for x in times)
    together = 1 / rate
    unit = "ghante" if re.search(r"hour|hr|ghant", t) else \
        "din" if re.search(r"day|din", t) else \
        "min" if re.search(r"min", t) else "units"
    ppl = " & ".join(_fmt(x) for x in times)
    return (f"{ppl} {unit} wale saath kaam karein to ~{together:.2f} {unit} "
            "me poora ho jayega.")
