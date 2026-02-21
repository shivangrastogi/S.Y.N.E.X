# BACKEND/automations/weather/weather_cmd.py
"""
Weather Command Handler with Settings-Driven Response Formatting
"""

from BACKEND.automations.weather.weather_service import get_weather
from BACKEND.automations.weather.weather_parser import parse_weather_query
from BACKEND.automations.weather.location_service import (
    get_current_location,
    get_default_location
)
from BACKEND.automations.weather.weather_config import settings


def weather_cmd(text: str, speak: bool = True) -> str:
    """
    Unified weather command handler with settings-driven formatting
    
    Args:
        text: User query text
        speak: If True, returns TTS-friendly string
    
    Returns:
        Formatted weather response string
    """
    try:
        # Parse query for city and unit
        city, unit = parse_weather_query(text)
        
        # Fall back to detected or default location
        if not city:
            city = get_current_location() or get_default_location()
        
        # Use default unit from settings if not specified in query
        if unit == "metric" and settings.default_unit != "metric":
            unit = settings.default_unit
        
        # Fetch weather data
        weather = get_weather(city, unit)
        
        # Format response based on settings
        unit_symbol = "°C" if unit == "metric" else "°F"
        speed_unit = "km/h" if unit == "metric" else "mph"
        
        if settings.use_short_response:
            # Brief response: "London: 15°C, cloudy"
            response = (
                f"{weather['city']}: "
                f"{weather['temperature']}{unit_symbol}, "
                f"{weather['description']}."
            )
        else:
            # Detailed response with configurable fields
            parts = [
                f"Weather in {weather['city']}: ",
                f"{weather['temperature']}{unit_symbol}"
            ]
            
            # Add feels-like if enabled
            if settings.include_feels_like:
                parts.append(f"feels like {weather['feels_like']}{unit_symbol}")
            
            # Add description
            parts.append(weather['description'])
            
            # Add humidity if enabled
            if settings.include_humidity:
                parts.append(f"humidity {weather['humidity']} percent")
            
            # Add wind if enabled
            if settings.include_wind:
                parts.append(f"wind speed {weather['wind_speed']} {speed_unit}")
            
            # Add pressure if enabled (optional, usually disabled)
            if settings.config.get("include_pressure", False):
                parts.append(f"pressure {weather['pressure']} hPa")
            
            # Add visibility if enabled (optional, usually disabled)
            if settings.config.get("include_visibility", False) and weather['visibility'] != "N/A":
                visibility_km = weather['visibility'] / 1000
                parts.append(f"visibility {visibility_km:.1f} km")
            
            # Join parts with appropriate punctuation
            response = parts[0] + ", ".join(parts[1:]) + "."
        
        return response
    
    except RuntimeError as e:
        # User-friendly error message
        error_msg = str(e)
        
        if "not found" in error_msg.lower():
            return f"I couldn't find weather data for {city}. Please check the city name."
        elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            return "Weather service is not configured properly. Please check your API key."
        elif "timeout" in error_msg.lower():
            return "Weather service is taking too long to respond. Please try again later."
        else:
            return "I can't fetch weather right now. Please try again later."
    
    except Exception as e:
        if settings.debug:
            print(f"❌ Weather command error: {e}")
        
        return (
            "I encountered an error while fetching weather. "
            "Please check your settings or try again later."
        )
