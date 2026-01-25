# BACKEND/automations/weather/weather_parser.py
import re

INVALID_CITIES = {
    "today", "tomorrow", "now", "outside", "here",
    "abhi", "aaj", "bahar", "please"
}


def parse_weather_query(text: str):
    """
    Parse weather query to extract city and unit.
    Returns: (city, unit)
    """
    text = text.lower().strip()

    # ---------------------------
    # UNIT DETECTION
    # ---------------------------
    unit = "metric"  # Celsius default

    if any(k in text for k in ["fahrenheit", "°f", "imperial"]):
        unit = "imperial"
    elif any(k in text for k in ["celsius", "°c", "metric"]):
        unit = "metric"

    # ---------------------------
    # CITY EXTRACTION PATTERNS
    # ---------------------------
    patterns = [
        r"weather in ([a-zA-Z\s]+)",
        r"temperature in ([a-zA-Z\s]+)",
        r"how(?:'s| is) the weather in ([a-zA-Z\s]+)",
        r"what(?:'s| is) the weather in ([a-zA-Z\s]+)",
        r"forecast for ([a-zA-Z\s]+)",
        r"climate in ([a-zA-Z\s]+)",
        r"([a-zA-Z\s]+)\s+ka\s+(?:weather|temperature|mausam)",  # Hinglish
    ]

    city = None

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            city = match.group(1).strip()
            break

    # ---------------------------
    # CLEAN CITY
    # ---------------------------
    if city:
        # Remove unit keywords first
        city = re.sub(
            r"\b(in\s+)?(celsius|fahrenheit|metric|imperial|°c|°f)\b",
            "",
            city,
            flags=re.IGNORECASE
        ).strip()
        
        # Remove time-related words
        city = re.sub(
            r"\b(today|tomorrow|now|please|outside|abhi|aaj|bahar)\b",
            "",
            city,
            flags=re.IGNORECASE
        ).strip()

        if city.lower() in INVALID_CITIES or len(city) < 3:
            city = None
        else:
            # Capitalize properly (e.g., "new york" -> "New York")
            city = " ".join(word.capitalize() for word in city.split())

    # ---------------------------
    # FALLBACK TO LOCATION
    # ---------------------------
    weather_keywords = [
        "weather", "temperature", "forecast",
        "climate", "hot", "cold", "mausam"
    ]

    if not city and any(k in text for k in weather_keywords):
        city = None

    return city, unit
