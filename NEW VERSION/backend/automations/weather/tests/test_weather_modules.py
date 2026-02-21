# BACKEND/automations/weather/tests/test_weather_modules.py
"""
Unit tests for Weather Modules (Service, Location, Parser)
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timedelta
import requests
import tempfile
import os

from BACKEND.automations.weather.weather_service import (
    get_weather,
    clear_weather_cache,
    _get_cache_key,
    _is_cache_valid,
    _weather_cache
)
from BACKEND.automations.weather.location_service import (
    get_current_location,
    get_default_location,
    clear_location_cache,
    _location_cache
)
from BACKEND.automations.weather.weather_parser import parse_weather_query
from BACKEND.automations.weather.weather_config import WeatherAutomationSettings


class TestWeatherService(unittest.TestCase):
    """Test weather service with caching and retry logic"""
    
    def setUp(self):
        """Clear cache before each test"""
        clear_weather_cache()
        
        # Reset settings
        WeatherAutomationSettings._instance = None
        self.settings = WeatherAutomationSettings()
        self.settings.enable_weather_cache = True
        self.settings.weather_cache_duration = 600
        self.settings.max_retries = 2
        self.settings.retry_delay = 0.1  # Fast retries for testing
        self.settings.request_timeout = 3
    
    def tearDown(self):
        """Clean up after tests"""
        clear_weather_cache()
        WeatherAutomationSettings._instance = None
    
    @patch('BACKEND.automations.weather.weather_service.requests.get')
    @patch('BACKEND.automations.weather.weather_service.get_env_required')
    def test_weather_fetch_success(self, mock_env, mock_get):
        """Test successful weather fetch"""
        mock_env.return_value = "test_api_key"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "London",
            "main": {
                "temp": 15.5,
                "feels_like": 14.2,
                "humidity": 70,
                "pressure": 1013
            },
            "weather": [{"description": "cloudy"}],
            "wind": {"speed": 5.2},
            "visibility": 10000,
            "sys": {"country": "GB"}
        }
        mock_get.return_value = mock_response
        
        result = get_weather("London")
        
        self.assertEqual(result["city"], "London")
        self.assertEqual(result["temperature"], 15.5)
        self.assertEqual(result["description"], "cloudy")
        self.assertEqual(result["humidity"], 70)
    
    @patch('BACKEND.automations.weather.weather_service.requests.get')
    @patch('BACKEND.automations.weather.weather_service.get_env_required')
    def test_weather_caching(self, mock_env, mock_get):
        """Test weather data is cached"""
        mock_env.return_value = "test_api_key"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Paris",
            "main": {"temp": 20.0, "feels_like": 19.0, "humidity": 60, "pressure": 1015},
            "weather": [{"description": "sunny"}],
            "wind": {"speed": 3.5},
            "sys": {"country": "FR"}
        }
        mock_get.return_value = mock_response
        
        # First call - should fetch from API
        result1 = get_weather("Paris")
        self.assertEqual(mock_get.call_count, 1)
        
        # Second call - should use cache
        result2 = get_weather("Paris")
        self.assertEqual(mock_get.call_count, 1)  # No additional API call
        
        self.assertEqual(result1, result2)
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        key1 = _get_cache_key("London", "metric")
        key2 = _get_cache_key("LONDON", "metric")
        key3 = _get_cache_key("London", "imperial")
        
        self.assertEqual(key1, key2)  # Case-insensitive
        self.assertNotEqual(key1, key3)  # Different units
    
    @patch('BACKEND.automations.weather.weather_service.requests.get')
    @patch('BACKEND.automations.weather.weather_service.get_env_required')
    def test_weather_retry_on_timeout(self, mock_env, mock_get):
        """Test retry logic on timeout"""
        mock_env.return_value = "test_api_key"
        
        # First call times out, second succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            Mock(status_code=200, json=lambda: {
                "name": "Tokyo",
                "main": {"temp": 25.0, "feels_like": 24.0, "humidity": 65, "pressure": 1010},
                "weather": [{"description": "clear"}],
                "wind": {"speed": 4.0},
                "sys": {"country": "JP"}
            })
        ]
        
        result = get_weather("Tokyo")
        
        self.assertEqual(result["city"], "Tokyo")
        self.assertEqual(mock_get.call_count, 2)  # Retry happened
    
    @patch('BACKEND.automations.weather.weather_service.requests.get')
    @patch('BACKEND.automations.weather.weather_service.get_env_required')
    def test_weather_city_not_found(self, mock_env, mock_get):
        """Test handling of city not found error"""
        mock_env.return_value = "test_api_key"
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with self.assertRaises(RuntimeError) as context:
            get_weather("InvalidCity123")
        
        self.assertIn("not found", str(context.exception))
    
    @patch('BACKEND.automations.weather.weather_service.requests.get')
    @patch('BACKEND.automations.weather.weather_service.get_env_required')
    def test_weather_max_retries_exceeded(self, mock_env, mock_get):
        """Test failure after max retries"""
        mock_env.return_value = "test_api_key"
        
        # All attempts fail
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with self.assertRaises(RuntimeError) as context:
            get_weather("London")
        
        self.assertIn("Failed to fetch weather", str(context.exception))
        self.assertEqual(mock_get.call_count, self.settings.max_retries + 1)
    
    def test_clear_cache(self):
        """Test cache clearing"""
        # Manually add to cache
        _weather_cache["test_key"] = {
            "data": {"temp": 20},
            "expires_at": datetime.now() + timedelta(hours=1)
        }
        
        self.assertIn("test_key", _weather_cache)
        
        clear_weather_cache()
        
        self.assertNotIn("test_key", _weather_cache)


class TestLocationService(unittest.TestCase):
    """Test location detection service"""
    
    def setUp(self):
        """Clear cache and reset settings"""
        # Import location service to access its settings reference
        from BACKEND.automations.weather import location_service as loc_service
        
        # Clear cache
        loc_service._location_cache = None
        
        # Get the singleton instance (don't reset it)
        self.settings = WeatherAutomationSettings()
        self.settings.enable_location_cache = False  # Disable caching in tests
        self.settings.auto_detect_location = True
    
    def tearDown(self):
        """Clean up"""
        clear_location_cache()
        # Don't reset singleton to avoid module-level import issues
    
    def test_default_location(self):
        """Test getting default location"""
        # Reset to known state
        self.settings.default_location = "London"
        
        location = get_default_location()
        self.assertEqual(location, "London")  # Default
    
    @patch('BACKEND.automations.weather.location_service.requests.get')
    def test_location_detection_success(self, mock_get):
        """Test successful location detection"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "city": "Mumbai"
        }
        mock_get.return_value = mock_response
        
        location = get_current_location()
        
        self.assertEqual(location, "Mumbai")
    
    @patch('BACKEND.automations.weather.location_service.requests.get')
    def test_location_caching(self, mock_get):
        """Test location is cached"""
        # Enable caching for this test only
        self.settings.enable_location_cache = True
        
        # Import and clear cache
        from BACKEND.automations.weather import location_service as loc_service
        loc_service._location_cache = None
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "city": "Berlin"
        }
        mock_get.return_value = mock_response
        
        # First call
        location1 = get_current_location()
        call_count_1 = mock_get.call_count
        
        # Second call - should use cache
        location2 = get_current_location()
        call_count_2 = mock_get.call_count
        
        self.assertEqual(location1, location2)
        self.assertEqual(call_count_1, call_count_2)  # No additional API call
    
    @patch('BACKEND.automations.weather.location_service.requests.get')
    def test_location_provider_fallback(self, mock_get):
        """Test fallback to secondary provider"""
        # First provider fails, second succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            Mock(status_code=200, json=lambda: {"city": "Sydney"})
        ]
        
        location = get_current_location()
        
        self.assertEqual(location, "Sydney")
        self.assertEqual(mock_get.call_count, 2)
    
    @patch('BACKEND.automations.weather.location_service.socket.gethostname')
    def test_location_auto_detect_disabled(self, mock_hostname):
        """Test when auto-detection is disabled"""
        # Mock hostname to ensure it doesn't interfere
        mock_hostname.return_value = "test-machine"
        
        # Import location service module and reset globals explicitly
        from BACKEND.automations.weather import location_service as loc_service
        
        # Clear the location cache completely
        loc_service._location_cache = None
        
        self.settings.auto_detect_location = False
        self.settings.default_location = "Paris"
        
        # Call directly without cache
        location = loc_service.get_current_location()
        
        self.assertEqual(location, "Paris")
    
    @patch('BACKEND.automations.weather.location_service.requests.get')
    @patch('BACKEND.automations.weather.location_service.socket.gethostname')
    def test_location_hostname_fallback(self, mock_hostname, mock_get):
        """Test hostname fallback when all providers fail"""
        # All API providers fail
        mock_get.side_effect = requests.exceptions.RequestException()
        
        # Hostname contains city name
        mock_hostname.return_value = "my-london-laptop"
        
        location = get_current_location()
        
        self.assertEqual(location, "London")
    
    def test_clear_location_cache(self):
        """Test clearing location cache"""
        global _location_cache
        
        # Manually set cache
        from BACKEND.automations.weather import location_service
        location_service._location_cache = {
            "city": "Test",
            "expires_at": datetime.now() + timedelta(hours=1)
        }
        
        clear_location_cache()
        
        self.assertIsNone(location_service._location_cache)


class TestWeatherParser(unittest.TestCase):
    """Test weather query parsing"""
    
    def test_parse_city_basic(self):
        """Test basic city extraction"""
        city, unit = parse_weather_query("weather in London")
        self.assertEqual(city, "London")
        self.assertEqual(unit, "metric")
    
    def test_parse_city_temperature(self):
        """Test temperature query parsing"""
        city, unit = parse_weather_query("temperature in New York")
        self.assertEqual(city, "New York")
    
    def test_parse_unit_fahrenheit(self):
        """Test Fahrenheit unit detection"""
        city, unit = parse_weather_query("weather in Paris in fahrenheit")
        self.assertEqual(city, "Paris")
        self.assertEqual(unit, "imperial")
    
    def test_parse_unit_celsius(self):
        """Test Celsius unit detection"""
        city, unit = parse_weather_query("weather in Tokyo in celsius")
        self.assertEqual(city, "Tokyo")
        self.assertEqual(unit, "metric")
    
    def test_parse_no_city(self):
        """Test query without city"""
        city, unit = parse_weather_query("what's the weather")
        self.assertIsNone(city)
        self.assertEqual(unit, "metric")
    
    def test_parse_invalid_city_filtering(self):
        """Test that invalid cities are filtered out"""
        city, unit = parse_weather_query("weather in today")
        self.assertIsNone(city)  # "today" is invalid
    
    def test_parse_hinglish_query(self):
        """Test Hinglish query parsing"""
        city, unit = parse_weather_query("Mumbai ka weather")
        self.assertEqual(city, "Mumbai")
    
    def test_parse_forecast_query(self):
        """Test forecast query"""
        city, unit = parse_weather_query("forecast for Berlin")
        self.assertEqual(city, "Berlin")
    
    def test_parse_climate_query(self):
        """Test climate query"""
        city, unit = parse_weather_query("climate in Sydney")
        self.assertEqual(city, "Sydney")
    
    def test_parse_question_format(self):
        """Test question format parsing"""
        city, unit = parse_weather_query("how's the weather in Mumbai")
        self.assertEqual(city, "Mumbai")
        
        city, unit = parse_weather_query("what is the weather in Delhi")
        self.assertEqual(city, "Delhi")
    
    def test_parse_short_city_rejected(self):
        """Test that very short city names are rejected"""
        city, unit = parse_weather_query("weather in AB")
        self.assertIsNone(city)  # Too short


if __name__ == "__main__":
    unittest.main()
