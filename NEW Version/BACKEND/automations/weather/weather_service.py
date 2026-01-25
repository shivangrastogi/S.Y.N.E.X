# BACKEND/automations/weather/weather_service.py
"""
Weather Service with Caching, Retry Logic, and Professional Error Handling
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from BACKEND.core.env_load.env_loader import get_env_required
from BACKEND.automations.weather.weather_config import settings


# Cache storage: {cache_key: {"data": weather_data, "expires_at": datetime}}
_weather_cache: Dict[str, dict] = {}


def _get_cache_key(city: str, unit: str) -> str:
    """Generate cache key for weather data"""
    return f"{city.lower()}_{unit}"


def _is_cache_valid(cache_key: str) -> bool:
    """Check if cached data is still valid"""
    if not settings.enable_weather_cache:
        return False
    
    if cache_key not in _weather_cache:
        return False
    
    cached = _weather_cache[cache_key]
    return datetime.now() < cached["expires_at"]


def _get_from_cache(cache_key: str) -> Optional[dict]:
    """Retrieve weather data from cache if valid"""
    if _is_cache_valid(cache_key):
        if settings.debug:
            print(f"🔥 Weather cache HIT for {cache_key}")
        return _weather_cache[cache_key]["data"]
    
    if settings.debug and cache_key in _weather_cache:
        print(f"⏰ Weather cache EXPIRED for {cache_key}")
    
    return None


def _save_to_cache(cache_key: str, data: dict):
    """Save weather data to cache"""
    if not settings.enable_weather_cache:
        return
    
    _weather_cache[cache_key] = {
        "data": data,
        "expires_at": datetime.now() + settings.weather_cache_duration
    }
    
    if settings.debug:
        print(f"💾 Weather cached for {cache_key} (expires in {settings.weather_cache_duration.total_seconds()}s)")


def clear_weather_cache():
    """Clear all cached weather data"""
    global _weather_cache
    _weather_cache.clear()
    if settings.debug:
        print("🧹 Weather cache cleared")


def get_weather(city: str, unit: str = "metric") -> dict:
    """
    Fetch weather data for a city with caching and retry logic
    
    Args:
        city: City name
        unit: "metric" (Celsius) or "imperial" (Fahrenheit)
    
    Returns:
        Dictionary with weather data
    
    Raises:
        RuntimeError: If weather fetch fails after retries
    """
    # Check cache first
    cache_key = _get_cache_key(city, unit)
    cached_data = _get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Fetch from API with retry logic
    api_key = get_env_required("OPENWEATHER_API_KEY")
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": unit
    }
    
    last_error = None
    
    for attempt in range(settings.max_retries + 1):
        try:
            if settings.debug and attempt > 0:
                print(f"🔄 Weather API retry {attempt}/{settings.max_retries} for {city}")
            
            response = requests.get(
                url, 
                params=params, 
                timeout=settings.request_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Parse and round temperature values
            decimal_places = 1 if settings.config["round_temperature"] else 2
            
            weather_data = {
                "city": data["name"],
                "temperature": round(data["main"]["temp"], decimal_places),
                "feels_like": round(data["main"]["feels_like"], decimal_places),
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "wind_speed": round(data["wind"]["speed"], decimal_places),
                "pressure": data["main"]["pressure"],
                "visibility": data.get("visibility", "N/A"),
                "country": data["sys"]["country"],
                "unit": unit
            }
            
            # Cache the result
            _save_to_cache(cache_key, weather_data)
            
            return weather_data
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise RuntimeError(f"City '{city}' not found. Please check the spelling.")
            elif e.response.status_code == 401:
                raise RuntimeError("Weather API authentication failed. Check your API key.")
            last_error = f"HTTP {e.response.status_code} error"
        
        except requests.exceptions.Timeout:
            last_error = "Request timed out"
        
        except requests.exceptions.ConnectionError:
            last_error = "Network connection error"
        
        except requests.exceptions.RequestException as e:
            last_error = f"Network error: {str(e)}"
        
        except KeyError as e:
            raise RuntimeError(f"Weather service returned unexpected data format (missing: {e})")
        
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
        
        # Wait before retry (except on last attempt)
        if attempt < settings.max_retries:
            time.sleep(settings.retry_delay)
    
    # All retries failed
    raise RuntimeError(f"Failed to fetch weather after {settings.max_retries + 1} attempts: {last_error}")