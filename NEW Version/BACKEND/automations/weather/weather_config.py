# BACKEND/automations/weather/weather_config.py
"""
Weather Automation Settings
Professional configuration management with JSON persistence
"""

import json
import os
from datetime import timedelta
from typing import Optional


class WeatherAutomationSettings:
    """
    Singleton settings manager for weather automation
    Provides caching, retry logic, and location preferences
    """
    
    _instance: Optional['WeatherAutomationSettings'] = None
    _config_path = os.path.join(
        os.path.dirname(__file__), 
        "weather_settings.json"
    )
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._config = self._load_config()
    
    def _get_defaults(self) -> dict:
        """Default configuration values"""
        return {
            # Caching
            "enable_weather_cache": True,
            "weather_cache_duration": 600,  # 10 minutes in seconds
            "enable_location_cache": True,
            "location_cache_duration": 3600,  # 1 hour in seconds
            
            # Retry Configuration
            "max_retries": 2,
            "retry_delay": 1.0,  # seconds
            "request_timeout": 6,  # seconds
            
            # Location Settings
            "default_location": "London",
            "auto_detect_location": True,
            "location_providers": [
                "http://ip-api.com/json",
                "https://ipinfo.io/json"
            ],
            
            # Weather Preferences
            "default_unit": "metric",  # metric (Celsius) or imperial (Fahrenheit)
            "include_feels_like": True,
            "include_humidity": True,
            "include_wind": True,
            "include_pressure": False,
            "include_visibility": False,
            
            # Response Formatting
            "use_short_response": False,  # Brief vs detailed weather
            "round_temperature": True,
            "decimal_places": 1,
            
            # API Configuration
            "weather_api_provider": "openweathermap",  # future: support multiple providers
            
            # Debug
            "debug": False
        }
    
    def _load_config(self) -> dict:
        """Load settings from JSON file or create defaults"""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new fields
                    defaults = self._get_defaults()
                    defaults.update(loaded)
                    return defaults
            except Exception as e:
                print(f"⚠️ Failed to load weather settings: {e}")
        
        return self._get_defaults()
    
    def _save_config(self):
        """Persist settings to JSON file"""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save weather settings: {e}")
    
    @property
    def config(self):
        """Read-only access to configuration"""
        return self._config.copy()
    
    # ==================== Caching ====================
    
    @property
    def enable_weather_cache(self) -> bool:
        return self._config["enable_weather_cache"]
    
    @enable_weather_cache.setter
    def enable_weather_cache(self, value: bool):
        self._config["enable_weather_cache"] = value
        self._save_config()
    
    @property
    def weather_cache_duration(self) -> timedelta:
        return timedelta(seconds=self._config["weather_cache_duration"])
    
    @weather_cache_duration.setter
    def weather_cache_duration(self, seconds: int):
        if seconds < 0:
            raise ValueError("Cache duration must be non-negative")
        self._config["weather_cache_duration"] = seconds
        self._save_config()
    
    @property
    def enable_location_cache(self) -> bool:
        return self._config["enable_location_cache"]
    
    @enable_location_cache.setter
    def enable_location_cache(self, value: bool):
        self._config["enable_location_cache"] = value
        self._save_config()
    
    @property
    def location_cache_duration(self) -> timedelta:
        return timedelta(seconds=self._config["location_cache_duration"])
    
    @location_cache_duration.setter
    def location_cache_duration(self, seconds: int):
        if seconds < 0:
            raise ValueError("Cache duration must be non-negative")
        self._config["location_cache_duration"] = seconds
        self._save_config()
    
    # ==================== Retry Logic ====================
    
    @property
    def max_retries(self) -> int:
        return self._config["max_retries"]
    
    @max_retries.setter
    def max_retries(self, value: int):
        if value < 0:
            raise ValueError("max_retries must be non-negative")
        self._config["max_retries"] = value
        self._save_config()
    
    @property
    def retry_delay(self) -> float:
        return self._config["retry_delay"]
    
    @retry_delay.setter
    def retry_delay(self, value: float):
        if value < 0:
            raise ValueError("retry_delay must be non-negative")
        self._config["retry_delay"] = value
        self._save_config()
    
    @property
    def request_timeout(self) -> int:
        return self._config["request_timeout"]
    
    @request_timeout.setter
    def request_timeout(self, value: int):
        if value < 1:
            raise ValueError("request_timeout must be at least 1 second")
        self._config["request_timeout"] = value
        self._save_config()
    
    # ==================== Location ====================
    
    @property
    def default_location(self) -> str:
        return self._config["default_location"]
    
    @default_location.setter
    def default_location(self, value: str):
        if not value or len(value) < 2:
            raise ValueError("default_location must be a valid city name")
        self._config["default_location"] = value
        self._save_config()
    
    @property
    def auto_detect_location(self) -> bool:
        return self._config["auto_detect_location"]
    
    @auto_detect_location.setter
    def auto_detect_location(self, value: bool):
        self._config["auto_detect_location"] = value
        self._save_config()
    
    @property
    def location_providers(self) -> list:
        return self._config["location_providers"].copy()
    
    # ==================== Weather Preferences ====================
    
    @property
    def default_unit(self) -> str:
        return self._config["default_unit"]
    
    @default_unit.setter
    def default_unit(self, value: str):
        if value not in ["metric", "imperial"]:
            raise ValueError("default_unit must be 'metric' or 'imperial'")
        self._config["default_unit"] = value
        self._save_config()
    
    @property
    def include_feels_like(self) -> bool:
        return self._config["include_feels_like"]
    
    @include_feels_like.setter
    def include_feels_like(self, value: bool):
        self._config["include_feels_like"] = value
        self._save_config()
    
    @property
    def include_humidity(self) -> bool:
        return self._config["include_humidity"]
    
    @include_humidity.setter
    def include_humidity(self, value: bool):
        self._config["include_humidity"] = value
        self._save_config()
    
    @property
    def include_wind(self) -> bool:
        return self._config["include_wind"]
    
    @include_wind.setter
    def include_wind(self, value: bool):
        self._config["include_wind"] = value
        self._save_config()
    
    @property
    def use_short_response(self) -> bool:
        return self._config["use_short_response"]
    
    @use_short_response.setter
    def use_short_response(self, value: bool):
        self._config["use_short_response"] = value
        self._save_config()
    
    # ==================== Debug ====================
    
    @property
    def debug(self) -> bool:
        return self._config["debug"]
    
    @debug.setter
    def debug(self, value: bool):
        self._config["debug"] = value
        self._save_config()
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self._config = self._get_defaults()
        self._save_config()


# Global singleton instance
settings = WeatherAutomationSettings()
