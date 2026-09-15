"""Weather lookup for any named city using Open-Meteo's geocoding API.

Complements ``weather_local`` (which always uses the configured default
location) — this one accepts an explicit city name parsed from the
spoken text. Cached per-city for 10 minutes.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request

from core.skill_registry import skill

log = logging.getLogger(__name__)


_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_TTL_S = 600.0
_CACHE: dict[str, tuple[float, str]] = {}  # city → (ts, text)

_WEATHER_CODES = {
    0: "clear",  1: "mostly clear",  2: "partly cloudy",  3: "overcast",
    45: "fog",   48: "depositing fog",
    51: "drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "rain",  63: "rain",     65: "heavy rain",
    71: "snow",  73: "snow",     75: "heavy snow",
    80: "showers", 81: "showers", 82: "heavy showers",
    95: "thunderstorm", 96: "thunderstorm + hail", 99: "thunderstorm + hail",
}


def _extract_city(text: str) -> str:
    """Pull a city name out of the raw user text. Patterns recognised:
        "weather in <city>"  / "<city> ka mausam" / "<city> ka weather"
        "weather for <city>"
        "what's the weather in <city>"
    Falls back to the whole text minus weather-trigger words.
    """
    if not text:
        return ""
    t = text.strip().lower()
    # English forms
    m = re.search(r"weather\s+(?:in|for|at|of)\s+([a-z][a-z\s.\-']{1,40})", t)
    if m:
        return m.group(1).strip(" ?.")
    # Hinglish: "<city> ka mausam" / "<city> ka weather"
    m = re.search(r"([a-z][a-z\s.\-']{1,40}?)\s+(?:ka|me|mein)\s+(?:mausam|weather)", t)
    if m:
        return m.group(1).strip(" ?.")
    # Hinglish: "mausam batao <city>" / "weather batao <city>"
    m = re.search(r"(?:mausam|weather)\s+batao\s+(?:in\s+)?([a-z][a-z\s.\-']{1,40})", t)
    if m:
        return m.group(1).strip(" ?.")
    return ""


def _geocode(city: str) -> tuple[float, float, str] | None:
    qs = urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
    try:
        with urllib.request.urlopen(f"{_GEO_URL}?{qs}", timeout=3.5) as r:
            data = json.loads(r.read())
    except Exception as e:
        log.info("[weather_for_city] geocode failed for %r: %s", city, e)
        return None
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    label = r.get("name") or city
    country = r.get("country") or ""
    if country:
        label = f"{label}, {country}"
    try:
        return float(r["latitude"]), float(r["longitude"]), label
    except (KeyError, TypeError, ValueError):
        return None


def _fetch_weather(lat: float, lon: float) -> dict | None:
    qs = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "weather_code,wind_speed_10m",
        "daily":   "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": "auto",
        "forecast_days": 1,
    })
    try:
        with urllib.request.urlopen(f"{_FORECAST_URL}?{qs}", timeout=3.5) as r:
            return json.loads(r.read())
    except Exception as e:
        log.info("[weather_for_city] forecast fetch failed: %s", e)
        return None


@skill(
    name="weather_for_city",
    description="Weather + today's forecast for a named city (Open-Meteo).",
    patterns=[
        "weather in", "weather for", "weather at",
        "what's the weather in", "what is the weather in",
        "mumbai ka mausam", "delhi ka mausam", "bangalore ka mausam",
        "kolkata ka weather", "chennai ka mausam",
        "weather in mumbai", "weather in delhi", "weather in bangalore",
        "weather for mumbai", "weather batao mumbai",
        "mausam batao delhi",
        "tokyo ka mausam", "london ka weather",
        "new york weather",
    ],
    required_entities=[],
)
def weather_for_city(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    city = _extract_city(text)
    if not city:
        return ("Kis sheher ka mausam? Bolo 'weather in Mumbai' "
                "ya 'Mumbai ka mausam'.")

    cache_key = city.lower()
    now = time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached and (now - cached[0]) < _TTL_S:
        return cached[1]

    geo = _geocode(city)
    if not geo:
        return f"'{city}' shahar nahi mila (geocoding fail)."
    lat, lon, label = geo
    data = _fetch_weather(lat, lon)
    if not data:
        return f"Weather fetch fail ho gaya for {label}."
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    code = int(cur.get("weather_code", 0))
    text_out = (
        f"{label}: {cur.get('temperature_2m', '—')}°C "
        f"(feels {cur.get('apparent_temperature', '—')}°C) · "
        f"{_WEATHER_CODES.get(code, 'unknown')} · "
        f"RH {cur.get('relative_humidity_2m', '—')}% · "
        f"wind {cur.get('wind_speed_10m', '—')} km/h · "
        f"today {(daily.get('temperature_2m_min') or [None])[0]}°/"
        f"{(daily.get('temperature_2m_max') or [None])[0]}°"
    )
    _CACHE[cache_key] = (now, text_out)
    return text_out
