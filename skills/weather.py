"""Real weather via OpenWeatherMap. Set OPENWEATHER_API_KEY env var."""

from __future__ import annotations

import os

import requests

from core.skill_registry import skill

_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()
_DEFAULT_CITY = os.environ.get("OPENWEATHER_DEFAULT_CITY", "Delhi")


@skill(
    name="real_weather",
    description="Live weather for a city (defaults to user's stored location or Delhi)",
    patterns=[
        "real weather batao",
        "actual weather kya hai",
        "live weather X",
        "X mein mausam kaisa hai",
        "weather of X",
    ],
    required_entities=[],
)
def real_weather(slots: dict) -> str:
    if not _API_KEY:
        return "Weather API key nahi hai. OPENWEATHER_API_KEY env var set karo."

    city = (slots.get("city") or slots.get("query") or _DEFAULT_CITY).strip()

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": _API_KEY, "units": "metric"}
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return f"{city} ka weather data fetch nahi ho paya."

    temp = data.get("main", {}).get("temp")
    feels = data.get("main", {}).get("feels_like")
    humidity = data.get("main", {}).get("humidity")
    desc = (data.get("weather") or [{}])[0].get("description", "")
    if temp is None:
        return f"{city} ka weather data adhura mila."
    return (
        f"{city} mein abhi {temp:.0f} degree hai, feel ho raha hai {feels:.0f}. "
        f"{desc.capitalize()}. Humidity {humidity}%."
    )
