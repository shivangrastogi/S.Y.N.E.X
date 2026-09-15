"""Offline unit converter — length, weight, temperature, volume, speed, data.

Pure arithmetic over a factor table (+ affine temperature). No network,
no lookups — a standalone assistant converts units on its own.
"""
from __future__ import annotations

import re
from typing import Optional

# unit alias → (dimension, canonical). Linear units convert via a factor
# to the dimension's BASE unit; temperature is handled separately (affine).
_BASE = {"length": "m", "weight": "g", "volume": "ml",
         "speed": "mps", "data": "b"}

# canonical unit → factor to base
_FACTORS: dict[str, tuple[str, float]] = {
    # length (base metre)
    "m": ("length", 1.0), "km": ("length", 1000.0),
    "cm": ("length", 0.01), "mm": ("length", 0.001),
    "mile": ("length", 1609.344), "yard": ("length", 0.9144),
    "foot": ("length", 0.3048), "inch": ("length", 0.0254),
    "nauticalmile": ("length", 1852.0),
    # weight (base gram)
    "g": ("weight", 1.0), "kg": ("weight", 1000.0), "mg": ("weight", 0.001),
    "lb": ("weight", 453.59237), "oz": ("weight", 28.349523125),
    "ton": ("weight", 1_000_000.0), "quintal": ("weight", 100_000.0),
    # volume (base ml)
    "ml": ("volume", 1.0), "litre": ("volume", 1000.0),
    "gallon": ("volume", 3785.411784), "cup": ("volume", 240.0),
    "pint": ("volume", 473.176473), "tbsp": ("volume", 14.7868),
    "tsp": ("volume", 4.92892),
    # speed (base m/s)
    "mps": ("speed", 1.0), "kmph": ("speed", 0.277778),
    "mph": ("speed", 0.44704), "knot": ("speed", 0.514444),
    # data (base byte)
    "b": ("data", 1.0), "kb": ("data", 1024.0), "mb": ("data", 1024.0**2),
    "gb": ("data", 1024.0**3), "tb": ("data", 1024.0**4),
    "bit": ("data", 0.125),
    # time (base second)
    "sec": ("time", 1.0), "min": ("time", 60.0), "hour": ("time", 3600.0),
    "day": ("time", 86400.0), "week": ("time", 604800.0),
    "year": ("time", 31_536_000.0),
}

# spoken alias → canonical
_ALIAS: dict[str, str] = {
    "meter": "m", "metre": "m", "meters": "m", "metres": "m",
    "kilometer": "km", "kilometre": "km", "kilometers": "km", "kms": "km",
    "centimeter": "cm", "centimetre": "cm", "millimeter": "mm",
    "miles": "mile", "mil": "mile", "feet": "foot", "ft": "foot",
    "inches": "inch", "in": "inch", "yards": "yard",
    "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "gram": "g", "grams": "g", "gm": "g", "milligram": "mg",
    "pound": "lb", "pounds": "lb", "paund": "lb", "lbs": "lb",
    "ounce": "oz", "ounces": "oz", "tonne": "ton", "tons": "ton",
    "liter": "litre", "liters": "litre", "litres": "litre", "ltr": "litre",
    "gallons": "gallon", "gal": "gallon", "cups": "cup",
    "celsius": "c", "centigrade": "c", "fahrenheit": "f", "kelvin": "k",
    "kmh": "kmph", "kph": "kmph", "kmhr": "kmph",
    "kilobyte": "kb", "megabyte": "mb", "gigabyte": "gb", "terabyte": "tb",
    "kilobytes": "kb", "megabytes": "mb", "gigabytes": "gb",
    "byte": "b", "bytes": "b", "bits": "bit",
    "knots": "knot", "nauticalmiles": "nauticalmile",
    # time
    "second": "sec", "seconds": "sec", "secs": "sec",
    "minute": "min", "minutes": "min", "mins": "min",
    "hours": "hour", "hr": "hour", "hrs": "hour", "ghanta": "hour", "ghante": "hour",
    "days": "day", "din": "day",
    "weeks": "week", "hafta": "week", "hafte": "week",
    "years": "year", "saal": "year",
}

_TEMP = {"c", "f", "k"}


def _canon(u: str) -> Optional[str]:
    u = u.strip().lower().rstrip(".")
    u = _ALIAS.get(u, u)
    if u in _FACTORS or u in _TEMP:
        return u
    return None


def _temp_to_c(v: float, u: str) -> float:
    return v if u == "c" else (v - 32) * 5 / 9 if u == "f" else v - 273.15


def _c_to(v_c: float, u: str) -> float:
    return v_c if u == "c" else v_c * 9 / 5 + 32 if u == "f" else v_c + 273.15


def convert(value: float, src: str, dst: str) -> Optional[float]:
    s, d = _canon(src), _canon(dst)
    if s is None or d is None:
        return None
    if s in _TEMP or d in _TEMP:
        if not (s in _TEMP and d in _TEMP):
            return None                      # can't mix temp with non-temp
        return _c_to(_temp_to_c(value, s), d)
    (dim_s, fs), (dim_d, fd) = _FACTORS[s], _FACTORS[d]
    if dim_s != dim_d:
        return None                          # dimension mismatch
    return value * fs / fd


def _fmt(n: float) -> str:
    if n == int(n):
        return str(int(n))
    return f"{n:.4g}"


_PARSE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*([a-z°]+)\s*"
    r"(?:me|mein|to|into|in|=|kitne?|kitna|barabar|equals?)\s*"
    r"(?:kitne?\s*)?([a-z°]+)",
    re.IGNORECASE)


def parse_and_convert(text: str) -> Optional[str]:
    """'10 km me kitne mile', '5 kg to pound', '100 f in c'."""
    t = (text or "").replace("°", " ").lower()
    m = _PARSE_RE.search(t)
    if not m:
        return None
    value = float(m.group(1))
    src, dst = m.group(2), m.group(3)
    if _canon(src) is None or _canon(dst) is None:
        return None
    out = convert(value, src, dst)
    if out is None:
        return ("Ye units aapas mein convert nahi hoti, sir (alag "
                "cheezein hain).")
    return f"{_fmt(value)} {src} = {_fmt(out)} {dst}."
