"""
Unit tests for YouTubeAutomationSettings configuration management
Tests singleton pattern, settings persistence, validation, and defaults
"""

import unittest
import os
from BACKEND.automations.youtube.youtube_automation_config import YouTubeAutomationSettings


class TestYouTubeAutomationSettings(unittest.TestCase):
    """Test suite for YouTubeAutomationSettings class"""

    def setUp(self):
        """Set up test fixtures"""
        YouTubeAutomationSettings._instance = None
        YouTubeAutomationSettings._initialized = False

    def tearDown(self):
        """Clean up test artifacts"""
        YouTubeAutomationSettings._instance = None
        YouTubeAutomationSettings._initialized = False

    # SINGLETON PATTERN TESTS
    def test_singleton_instance(self):
        """Test that only one instance of settings exists"""
        settings1 = YouTubeAutomationSettings()
        settings2 = YouTubeAutomationSettings()
        self.assertIs(settings1, settings2)

    # DEFAULT VALUES TESTS
    def test_browser_value_is_valid(self):
        """Test browser value is one of the valid options"""
        settings = YouTubeAutomationSettings()
        self.assertIn(settings.browser, ["brave", "edge", "chrome"])

    def test_quality_value_is_valid(self):
        """Test quality value is one of the valid options"""
        settings = YouTubeAutomationSettings()
        self.assertIn(settings.default_quality, ["auto", "1080p", "720p", "480p", "360p"])

    def test_player_settings_exist(self):
        """Test player settings have valid values"""
        settings = YouTubeAutomationSettings()
        self.assertGreater(settings.default_speed, 0.2)
        self.assertLess(settings.default_speed, 2.1)
        self.assertGreaterEqual(settings.default_volume, 0.0)
        self.assertLessEqual(settings.default_volume, 1.0)
        self.assertIsInstance(settings.auto_play, bool)

    def test_default_timeout_settings(self):
        """Test default timeout configuration"""
        settings = YouTubeAutomationSettings()
        self.assertEqual(settings.search_timeout, 20)
        self.assertEqual(settings.player_load_timeout, 15)

    def test_default_retry_settings(self):
        """Test default retry configuration"""
        settings = YouTubeAutomationSettings()
        self.assertEqual(settings.max_retries, 2)
        self.assertEqual(settings.retry_delay, 3)

    # PROPERTY SETTER TESTS
    def test_browser_property_setter(self):
        """Test setting browser property"""
        settings = YouTubeAutomationSettings()
        settings.browser = "chrome"
        self.assertEqual(settings.browser, "chrome")

    def test_speed_property_setter(self):
        """Test setting default_speed property"""
        settings = YouTubeAutomationSettings()
        settings.default_speed = 1.5
        self.assertEqual(settings.default_speed, 1.5)

    def test_volume_property_setter(self):
        """Test setting default_volume property"""
        settings = YouTubeAutomationSettings()
        settings.default_volume = 0.8
        self.assertEqual(settings.default_volume, 0.8)

    def test_quality_property_setter(self):
        """Test setting default_quality property"""
        settings = YouTubeAutomationSettings()
        settings.default_quality = "720p"
        self.assertEqual(settings.default_quality, "720p")

    # VALIDATION TESTS
    def test_invalid_browser_validation(self):
        """Test browser validation rejects invalid values"""
        settings = YouTubeAutomationSettings()
        with self.assertRaises(ValueError):
            settings.browser = "invalid_browser"

    def test_invalid_quality_validation(self):
        """Test quality validation rejects invalid values"""
        settings = YouTubeAutomationSettings()
        with self.assertRaises(ValueError):
            settings.default_quality = "invalid_quality"

    def test_invalid_speed_validation(self):
        """Test speed validation rejects out-of-range values"""
        settings = YouTubeAutomationSettings()
        with self.assertRaises(ValueError):
            settings.default_speed = 3.0  # Max is 2.0

    def test_invalid_volume_validation(self):
        """Test volume validation rejects out-of-range values"""
        settings = YouTubeAutomationSettings()
        with self.assertRaises(ValueError):
            settings.default_volume = 1.5  # Max is 1.0

    def test_invalid_retry_validation(self):
        """Test retry validation rejects invalid values"""
        settings = YouTubeAutomationSettings()
        with self.assertRaises(ValueError):
            settings.max_retries = 10  # Max is 5

    # UTILITY METHOD TESTS
    def test_get_all_settings(self):
        """Test getting all settings"""
        settings = YouTubeAutomationSettings()
        all_settings = settings.get_all_settings()
        
        self.assertIsInstance(all_settings, dict)
        self.assertIn("browser", all_settings)
        self.assertIn("default_speed", all_settings)

    def test_update_settings(self):
        """Test updating multiple settings at once"""
        settings = YouTubeAutomationSettings()
        updates = {"browser": "chrome", "default_speed": 1.25}
        settings.update_settings(updates)
        
        self.assertEqual(settings.browser, "chrome")
        self.assertEqual(settings.default_speed, 1.25)

    # BOUNDARY TESTS
    def test_boundary_speed_values(self):
        """Test boundary speed values"""
        settings = YouTubeAutomationSettings()
        settings.default_speed = 0.25
        self.assertEqual(settings.default_speed, 0.25)
        settings.default_speed = 2.0
        self.assertEqual(settings.default_speed, 2.0)

    def test_all_quality_options(self):
        """Test all valid quality options"""
        settings = YouTubeAutomationSettings()
        valid_qualities = ["auto", "1080p", "720p", "480p", "360p"]
        for quality in valid_qualities:
            settings.default_quality = quality
            self.assertEqual(settings.default_quality, quality)

    # DEBUG MODE TESTS
    def test_debug_mode_setting(self):
        """Test debug mode can be toggled"""
        settings = YouTubeAutomationSettings()
        original_debug = settings.debug_mode
        settings.debug_mode = not original_debug
        self.assertEqual(settings.debug_mode, not original_debug)


if __name__ == '__main__':
    unittest.main(verbosity=2)
