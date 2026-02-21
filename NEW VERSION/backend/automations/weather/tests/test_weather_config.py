# BACKEND/automations/weather/tests/test_weather_config.py
"""
Unit tests for Weather Automation Settings
"""

import unittest
import os
import json
import tempfile
from datetime import timedelta
from BACKEND.automations.weather.weather_config import WeatherAutomationSettings


class TestWeatherConfig(unittest.TestCase):
    """Test weather configuration management"""
    
    def setUp(self):
        """Create a temporary config file for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_config = os.path.join(self.temp_dir, "test_weather_settings.json")
        
        # Override the config path for testing
        WeatherAutomationSettings._config_path = self.temp_config
        
        # Reset singleton
        WeatherAutomationSettings._instance = None
        self.settings = WeatherAutomationSettings()
    
    def tearDown(self):
        """Clean up temp files"""
        if os.path.exists(self.temp_config):
            os.remove(self.temp_config)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
        
        # Reset singleton
        WeatherAutomationSettings._instance = None
    
    def test_default_config(self):
        """Test default configuration values"""
        self.assertTrue(self.settings.enable_weather_cache)
        self.assertEqual(self.settings.weather_cache_duration, timedelta(seconds=600))
        self.assertTrue(self.settings.enable_location_cache)
        self.assertEqual(self.settings.location_cache_duration, timedelta(seconds=3600))
        self.assertEqual(self.settings.max_retries, 2)
        self.assertEqual(self.settings.retry_delay, 1.0)
        self.assertEqual(self.settings.request_timeout, 6)
        self.assertEqual(self.settings.default_location, "London")
        self.assertTrue(self.settings.auto_detect_location)
        self.assertEqual(self.settings.default_unit, "metric")
        self.assertTrue(self.settings.include_feels_like)
        self.assertTrue(self.settings.include_humidity)
        self.assertTrue(self.settings.include_wind)
        self.assertFalse(self.settings.use_short_response)
        self.assertFalse(self.settings.debug)
    
    def test_singleton_pattern(self):
        """Test that only one instance exists"""
        settings1 = WeatherAutomationSettings()
        settings2 = WeatherAutomationSettings()
        self.assertIs(settings1, settings2)
    
    def test_enable_disable_weather_cache(self):
        """Test enabling/disabling weather cache"""
        self.settings.enable_weather_cache = False
        self.assertFalse(self.settings.enable_weather_cache)
        
        self.settings.enable_weather_cache = True
        self.assertTrue(self.settings.enable_weather_cache)
    
    def test_weather_cache_duration(self):
        """Test weather cache duration modification"""
        self.settings.weather_cache_duration = 300  # 5 minutes
        self.assertEqual(self.settings.weather_cache_duration, timedelta(seconds=300))
        
        # Test validation
        with self.assertRaises(ValueError):
            self.settings.weather_cache_duration = -10
    
    def test_location_cache_duration(self):
        """Test location cache duration modification"""
        self.settings.location_cache_duration = 1800  # 30 minutes
        self.assertEqual(self.settings.location_cache_duration, timedelta(seconds=1800))
    
    def test_max_retries(self):
        """Test max retries setting"""
        self.settings.max_retries = 3
        self.assertEqual(self.settings.max_retries, 3)
        
        # Test validation
        with self.assertRaises(ValueError):
            self.settings.max_retries = -1
    
    def test_retry_delay(self):
        """Test retry delay setting"""
        self.settings.retry_delay = 2.5
        self.assertEqual(self.settings.retry_delay, 2.5)
        
        # Test validation
        with self.assertRaises(ValueError):
            self.settings.retry_delay = -0.5
    
    def test_request_timeout(self):
        """Test request timeout setting"""
        self.settings.request_timeout = 10
        self.assertEqual(self.settings.request_timeout, 10)
        
        # Test validation
        with self.assertRaises(ValueError):
            self.settings.request_timeout = 0
    
    def test_default_location(self):
        """Test default location setting"""
        self.settings.default_location = "New York"
        self.assertEqual(self.settings.default_location, "New York")
        
        # Test validation
        with self.assertRaises(ValueError):
            self.settings.default_location = ""
        
        with self.assertRaises(ValueError):
            self.settings.default_location = "A"  # Too short
    
    def test_auto_detect_location(self):
        """Test auto-detection toggle"""
        self.settings.auto_detect_location = False
        self.assertFalse(self.settings.auto_detect_location)
        
        self.settings.auto_detect_location = True
        self.assertTrue(self.settings.auto_detect_location)
    
    def test_default_unit(self):
        """Test default unit setting"""
        self.settings.default_unit = "imperial"
        self.assertEqual(self.settings.default_unit, "imperial")
        
        self.settings.default_unit = "metric"
        self.assertEqual(self.settings.default_unit, "metric")
        
        # Test validation
        with self.assertRaises(ValueError):
            self.settings.default_unit = "kelvin"
    
    def test_response_preferences(self):
        """Test response formatting preferences"""
        self.settings.include_feels_like = False
        self.assertFalse(self.settings.include_feels_like)
        
        self.settings.include_humidity = False
        self.assertFalse(self.settings.include_humidity)
        
        self.settings.include_wind = False
        self.assertFalse(self.settings.include_wind)
        
        self.settings.use_short_response = True
        self.assertTrue(self.settings.use_short_response)
    
    def test_debug_mode(self):
        """Test debug mode toggle"""
        self.settings.debug = True
        self.assertTrue(self.settings.debug)
        
        self.settings.debug = False
        self.assertFalse(self.settings.debug)
    
    def test_persistence(self):
        """Test that settings persist to file"""
        self.settings.default_location = "Tokyo"
        self.settings.max_retries = 5
        self.settings.default_unit = "imperial"
        
        # Verify file was created
        self.assertTrue(os.path.exists(self.temp_config))
        
        # Load from file
        with open(self.temp_config, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data["default_location"], "Tokyo")
        self.assertEqual(data["max_retries"], 5)
        self.assertEqual(data["default_unit"], "imperial")
    
    def test_load_from_file(self):
        """Test loading settings from existing file"""
        # Create a config file
        config_data = {
            "default_location": "Paris",
            "max_retries": 4,
            "weather_cache_duration": 900,
            "default_unit": "imperial"
        }
        
        with open(self.temp_config, 'w') as f:
            json.dump(config_data, f)
        
        # Reset and reload
        WeatherAutomationSettings._instance = None
        settings = WeatherAutomationSettings()
        
        self.assertEqual(settings.default_location, "Paris")
        self.assertEqual(settings.max_retries, 4)
        self.assertEqual(settings.weather_cache_duration, timedelta(seconds=900))
        self.assertEqual(settings.default_unit, "imperial")
    
    def test_reset_to_defaults(self):
        """Test resetting to default values"""
        self.settings.default_location = "Mumbai"
        self.settings.max_retries = 10
        self.settings.debug = True
        
        self.settings.reset_to_defaults()
        
        self.assertEqual(self.settings.default_location, "London")
        self.assertEqual(self.settings.max_retries, 2)
        self.assertFalse(self.settings.debug)
    
    def test_location_providers_list(self):
        """Test location providers is a list"""
        providers = self.settings.location_providers
        self.assertIsInstance(providers, list)
        self.assertGreater(len(providers), 0)
        
        # Ensure we get a copy (not direct reference)
        providers.append("http://test.com")
        self.assertNotIn("http://test.com", self.settings.location_providers)


if __name__ == "__main__":
    unittest.main()
