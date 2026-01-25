# BACKEND/automations/weather/location_service.py
"""
Location Service with Caching and Multi-Provider Fallback
"""

import requests
import socket
from datetime import datetime, timedelta
from typing import Optional
from BACKEND.automations.weather.weather_config import settings


# Cache storage
_location_cache: Optional[dict] = None


def _is_location_cache_valid() -> bool:
    """Check if cached location is still valid"""
    if not settings.enable_location_cache or _location_cache is None:
        return False
    
    return datetime.now() < _location_cache["expires_at"]


def _get_location_from_cache() -> Optional[str]:
    """Retrieve location from cache if valid"""
    if _is_location_cache_valid():
        if settings.debug:
            print(f"🔥 Location cache HIT: {_location_cache['city']}")
        return _location_cache["city"]
    
    if settings.debug and _location_cache:
        print("⏰ Location cache EXPIRED")
    
    return None


def _save_location_to_cache(city: str):
    """Save location to cache"""
    global _location_cache
    
    if not settings.enable_location_cache:
        return
    
    _location_cache = {
        "city": city,
        "expires_at": datetime.now() + settings.location_cache_duration
    }
    
    if settings.debug:
        print(f"💾 Location cached: {city} (expires in {settings.location_cache_duration.total_seconds()}s)")


def clear_location_cache():
    """Clear cached location data"""
    global _location_cache
    _location_cache = None
    if settings.debug:
        print("🧹 Location cache cleared")


def get_current_location() -> Optional[str]:
    """
    Get current city location using IP-based geolocation with caching
    
    Returns:
        City name or None if detection fails
    """
    # Check cache first
    cached_location = _get_location_from_cache()
    if cached_location:
        return cached_location
    
    if not settings.auto_detect_location:
        if settings.debug:
            print("📍 Auto-detection disabled, using default location")
        return settings.default_location
    
    # Try each provider in order
    for provider_url in settings.location_providers:
        try:
            if settings.debug:
                print(f"🌐 Trying location provider: {provider_url}")
            
            response = requests.get(
                provider_url, 
                timeout=settings.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different provider formats
                city = None
                
                # ip-api.com format
                if "status" in data and data.get("status") == "success":
                    city = data.get("city")
                # ipinfo.io format
                elif "city" in data:
                    city = data.get("city")
                
                if city:
                    if settings.debug:
                        print(f"✅ Location detected: {city}")
                    _save_location_to_cache(city)
                    return city
        
        except requests.exceptions.Timeout:
            if settings.debug:
                print(f"⏰ Timeout for {provider_url}")
            continue
        
        except requests.exceptions.RequestException as e:
            if settings.debug:
                print(f"❌ Provider {provider_url} failed: {e}")
            continue
        
        except Exception as e:
            if settings.debug:
                print(f"❌ Unexpected error with {provider_url}: {e}")
            continue
    
    # All providers failed, try hostname fallback
    try:
        hostname = socket.gethostname()
        common_cities = [
            "london", "newyork", "paris", "tokyo", "mumbai", "delhi",
            "sydney", "berlin", "toronto", "singapore", "bangalore"
        ]
        
        for city in common_cities:
            if city in hostname.lower():
                detected = city.capitalize()
                if settings.debug:
                    print(f"🖥️ Location from hostname: {detected}")
                _save_location_to_cache(detected)
                return detected
    except Exception as e:
        if settings.debug:
            print(f"❌ Hostname detection failed: {e}")
    
    if settings.debug:
        print("❌ All location detection methods failed")
    
    return None


def get_default_location() -> str:
    """
    Return the configured default location
    
    Returns:
        Default city name from settings
    """
    return settings.default_location