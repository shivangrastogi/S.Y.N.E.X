"""Info + utility skills — weather (no API key), currency, screen color.

* ``weather_local``      — open-meteo (no key required); cached 10 min
* ``currency_convert``   — exchangerate.host fallback to hardcoded snapshot
* ``screen_color_pick``  — ctypes GetPixel at cursor, copy hex to clipboard
* ``date_diff``          — "days between 2026-01-01 and today"
"""
from __future__ import annotations

import ctypes
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


# ── weather_local ──────────────────────────────────────────────────── #

# Default: Delhi. User can override via settings.json:
#   "weather_lat": 28.61, "weather_lon": 77.21, "weather_label": "Delhi"
_DEFAULT_LAT = 28.6139
_DEFAULT_LON = 77.2090
_DEFAULT_LABEL = "Delhi"

_WX_CACHE = {"ts": 0.0, "text": ""}
_WX_TTL_S = 600.0   # 10 min


_WEATHER_CODES = {
    0: "clear",  1: "mostly clear",  2: "partly cloudy",  3: "overcast",
    45: "fog",   48: "depositing fog",
    51: "drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "rain",  63: "rain",     65: "heavy rain",
    71: "snow",  73: "snow",     75: "heavy snow",
    80: "showers", 81: "showers", 82: "heavy showers",
    95: "thunderstorm", 96: "thunderstorm + hail", 99: "thunderstorm + hail",
}


@skill(
    name="weather_local",
    description="Current weather + today's forecast (open-meteo, no API key)",
    patterns=[
        "weather", "today's weather", "weather batao", "mausam",
        "outside temperature", "kitni garmi hai", "kitna cold hai",
        "current temperature", "weather kaisa hai", "aaj ka mausam",
    ],
)
def weather_local(_slots: dict) -> str:
    now = time.monotonic()
    if (now - _WX_CACHE["ts"]) < _WX_TTL_S and _WX_CACHE["text"]:
        return _WX_CACHE["text"]
    try:
        from core import settings as _settings
        lat = float(_settings.get("weather_lat", _DEFAULT_LAT))
        lon = float(_settings.get("weather_lon", _DEFAULT_LON))
        label = str(_settings.get("weather_label", _DEFAULT_LABEL))
    except Exception:
        lat, lon, label = _DEFAULT_LAT, _DEFAULT_LON, _DEFAULT_LABEL
    qs = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "weather_code,wind_speed_10m",
        "daily":   "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": "auto",
        "forecast_days": 1,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=3.5) as r:
            import json
            data = json.loads(r.read())
    except Exception as e:
        return f"Weather fetch fail ho gaya: {e}"
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    code = int(cur.get("weather_code", 0))
    text = (
        f"{label}: {cur.get('temperature_2m', '—')}°C "
        f"(feels {cur.get('apparent_temperature', '—')}°C) · "
        f"{_WEATHER_CODES.get(code, 'unknown')} · "
        f"RH {cur.get('relative_humidity_2m', '—')}% · "
        f"wind {cur.get('wind_speed_10m', '—')} km/h · "
        f"today {(daily.get('temperature_2m_min') or [None])[0]}°/"
        f"{(daily.get('temperature_2m_max') or [None])[0]}°"
    )
    _WX_CACHE.update({"ts": now, "text": text})
    return text


# ── currency_convert ───────────────────────────────────────────────── #

# Frozen snapshot — usable offline. Live mode uses exchangerate.host with
# a 30 min cache; fail-quietly falls back to this table.
_RATE_SNAPSHOT = {
    "USD": 1.0, "EUR": 0.92, "GBP": 0.79, "INR": 83.4,
    "JPY": 151.0, "AUD": 1.53, "CAD": 1.37, "CHF": 0.89,
    "CNY": 7.24, "SGD": 1.34, "AED": 3.67, "BRL": 5.05,
}
_RATE_CACHE = {"ts": 0.0, "rates": dict(_RATE_SNAPSHOT)}
_RATE_TTL_S = 30 * 60


_CONV_RE = re.compile(
    r"(?P<amt>[\d,]+(?:\.\d+)?)\s*(?P<src>[a-z]{3})\s+(?:to|in|->|→)\s+(?P<dst>[a-z]{3})",
    re.I,
)


def _refresh_rates() -> dict:
    now = time.monotonic()
    if (now - _RATE_CACHE["ts"]) < _RATE_TTL_S:
        return _RATE_CACHE["rates"]
    try:
        with urllib.request.urlopen(
            "https://api.exchangerate.host/latest?base=USD", timeout=2.5
        ) as r:
            import json
            data = json.loads(r.read())
        rates = {str(k).upper(): float(v) for k, v in (data.get("rates") or {}).items()}
        if rates:
            _RATE_CACHE.update({"ts": now, "rates": rates})
    except Exception:
        # Stay on snapshot.
        pass
    return _RATE_CACHE["rates"]


@skill(
    name="currency_convert",
    description="Convert between currencies (e.g. '100 usd to inr')",
    patterns=[
        "convert currency", "currency convert", "100 usd to inr",
        "convert 50 eur to usd", "exchange rate",
        "kitne ka hai", "convert", "exchange",
    ],
    required_entities=["content"],
    prompts={"content": "Format: '100 usd to inr'"},
)
def currency_convert(slots: dict) -> str:
    raw = (slots.get("content") or "").strip()
    m = _CONV_RE.search(raw)
    if not m:
        return "Format: '100 usd to inr'."
    amt = float(m.group("amt").replace(",", ""))
    src = m.group("src").upper()
    dst = m.group("dst").upper()
    rates = _refresh_rates()
    if src not in rates or dst not in rates:
        return f"Currency {src} or {dst} not supported. Known: {', '.join(sorted(rates)[:12])}…"
    # USD pivot — table is "1 USD = X currency".
    usd_amount = amt / rates[src]
    result = usd_amount * rates[dst]
    fresh = (time.monotonic() - _RATE_CACHE["ts"]) < _RATE_TTL_S
    src_note = "" if fresh else " (offline snapshot)"
    return f"{amt:,.2f} {src} = {result:,.2f} {dst}{src_note}"


# ── screen_color_pick ──────────────────────────────────────────────── #

@skill(
    name="screen_color_pick",
    description="Read the pixel under the cursor and copy hex to clipboard",
    patterns=[
        "pick color", "color pick", "screen color", "color pick karo",
        "what color is this", "hex color", "color picker",
    ],
)
def screen_color_pick(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Color picker sirf Windows pe."
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return "Cursor position read nahi hua."
        hdc = user32.GetDC(0)
        try:
            colorref = gdi32.GetPixel(hdc, pt.x, pt.y)
        finally:
            user32.ReleaseDC(0, hdc)
        if colorref == 0xFFFFFFFF:
            return "Pixel read fail ho gaya (out of bounds?)."
        # COLORREF is 0x00BBGGRR.
        r = colorref & 0xFF
        g = (colorref >> 8) & 0xFF
        b = (colorref >> 16) & 0xFF
        hex_str = f"#{r:02X}{g:02X}{b:02X}"
        rgb_str = f"rgb({r}, {g}, {b})"
        try:
            import pyperclip
            pyperclip.copy(hex_str)
            copied = " (copied to clipboard)"
        except Exception:
            copied = ""
        return f"Color at ({pt.x},{pt.y}): {hex_str} · {rgb_str}{copied}"
    except Exception as e:
        return f"Color pick fail: {e}"


# ── date_diff ──────────────────────────────────────────────────────── #

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|today|tomorrow|yesterday", re.I)


def _parse_date(token: str) -> Optional[date]:
    t = token.strip().lower()
    today = date.today()
    if t == "today":
        return today
    if t == "tomorrow":
        from datetime import timedelta
        return today + timedelta(days=1)
    if t == "yesterday":
        from datetime import timedelta
        return today - timedelta(days=1)
    try:
        return datetime.strptime(t, "%Y-%m-%d").date()
    except ValueError:
        return None


@skill(
    name="date_diff",
    description="Days between two dates ('days between 2026-01-01 and today')",
    patterns=[
        "days between", "date diff", "how many days",
        "kitne din", "date difference",
    ],
    required_entities=["content"],
    prompts={"content": "Format: 'YYYY-MM-DD and YYYY-MM-DD' (or 'today' / 'tomorrow' / 'yesterday')"},
)
def date_diff(slots: dict) -> str:
    raw = (slots.get("content") or "").strip()
    tokens = _DATE_RE.findall(raw)
    if len(tokens) < 2:
        return "Do dates chahiye. Format: '2026-01-01 and today'."
    d1 = _parse_date(tokens[0])
    d2 = _parse_date(tokens[1])
    if d1 is None or d2 is None:
        return "Date parse nahi hua. Use 'YYYY-MM-DD' or 'today'/'tomorrow'/'yesterday'."
    delta = (d2 - d1).days
    return f"{d1} to {d2}: {delta:+d} day(s)"
