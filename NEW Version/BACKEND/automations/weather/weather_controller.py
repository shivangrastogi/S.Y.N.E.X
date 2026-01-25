# BACKEND/automations/weather/weather_controller.py
"""
Weather Automation Controller
Unified interface for weather operations with intent handling
"""

from typing import Optional
from BACKEND.automations.weather.weather_cmd import weather_cmd
from BACKEND.automations.weather.weather_service import clear_weather_cache
from BACKEND.automations.weather.location_service import clear_location_cache
from BACKEND.automations.weather.weather_config import settings


class WeatherController:
    """
    Professional weather automation controller
    Handles intent routing and provides cache management
    """
    
    def __init__(self):
        """Initialize weather controller"""
        pass
    
    def handle(self, intent: str, text: str = "") -> Optional[str]:
        """
        Handle weather-related intents
        
        Args:
            intent: Intent identifier (e.g., "check_weather", "check_temperature")
            text: Original user query text
        
        Returns:
            Response string or None if intent not handled
        """
        try:
            # Check weather intents
            if intent in ["check_weather", "check_temperature", "weather_query", 
                          "get_weather", "weather_forecast"]:
                return weather_cmd(text, speak=True)
            
        except Exception as e:
            if settings.debug:
                print(f"❌ WeatherController error for intent '{intent}': {e}")
            return "I encountered an error while fetching weather information."
        
        return None
    
    def get_weather(self, query: str) -> str:
        """
        Direct method to get weather
        
        Args:
            query: Weather query text
        
        Returns:
            Formatted weather response
        """
        return weather_cmd(query, speak=True)
    
    def clear_caches(self):
        """Clear all weather-related caches"""
        clear_weather_cache()
        clear_location_cache()
        
        if settings.debug:
            print("🧹 All weather caches cleared")
    
    def get_settings(self) -> dict:
        """
        Get current weather automation settings
        
        Returns:
            Dictionary of current settings
        """
        return settings.config
    
    def update_setting(self, key: str, value) -> bool:
        """
        Update a specific setting
        
        Args:
            key: Setting name
            value: New value
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if hasattr(settings, key):
                setattr(settings, key, value)
                return True
            return False
        except Exception as e:
            if settings.debug:
                print(f"❌ Failed to update setting '{key}': {e}")
            return False
