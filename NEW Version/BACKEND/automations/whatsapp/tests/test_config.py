# BACKEND/automations/whatsapp/tests/test_config.py
"""
Unit tests for WhatsApp Automation Settings
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch

from BACKEND.automations.whatsapp.whatsapp_automation_config import (
    WhatsAppAutomationSettings,
    get_settings
)


class TestWhatsAppAutomationSettings(unittest.TestCase):
    """Test cases for WhatsAppAutomationSettings singleton"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test environment"""
        # Create temp directory for test config
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_config_file = os.path.join(cls.temp_dir, "whatsapp_settings.json")
        
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test environment"""
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)

    def setUp(self):
        """Reset settings before each test"""
        # Reset singleton instance to defaults
        settings = WhatsAppAutomationSettings()
        settings._settings = {
            "preferred_backend": "auto",
            "fallback_enabled": True,
            "auto_detect_desktop": True,
            "browser": "edge",
            "browser_profile": "Default",
            "browser_user_data_dir": "",
            "desktop_launch_timeout": 10,
            "desktop_ready_timeout": 40,
            "desktop_launch_methods": ["direct", "uri", "explorer"],
            "web_load_delay": 15,
            "web_ready_timeout": 30,
            "web_qr_scan_timeout": 120,
            "typing_interval": 0.05,
            "send_delay": 0.5,
            "message_max_length": 5000,
            "allow_empty_messages": False,
            "retry_enabled": True,
            "max_retries": 2,
            "retry_delay": 3,
            "retry_backoff_multiplier": 2.0,
            "contact_validation_enabled": True,
            "contact_min_length": 1,
            "contact_max_length": 100,
            "normalize_contact_names": True,
            "bring_window_to_front": True,
            "minimize_after_send": False,
            "close_after_send": False,
            "ui_prime_delay": 0.3,
            "search_clear_delay": 0.3,
            "chat_open_delay": 1.2,
            "global_timeout": 120,
            "enable_message_queue": False,
            "queue_max_size": 50,
            "enable_scheduling": False,
            "enable_attachments": False,
            "debug_mode": False,
            "verbose_logging": False,
            "screenshot_on_error": False,
            "log_pyautogui_actions": False,
            "cache_contact_searches": False,
            "contact_cache_duration": 300,
            "screenshot_on_failure": False,
            "save_failed_messages": True,
            "failed_messages_file": "failed_whatsapp_messages.json",
            "parallel_message_sending": False,
            "max_parallel_messages": 3,
            "support_hinglish": True,
            "support_unicode": True,
        }

    def test_singleton_pattern(self):
        """Test that WhatsAppAutomationSettings is a singleton"""
        settings1 = WhatsAppAutomationSettings()
        settings2 = WhatsAppAutomationSettings()
        self.assertIs(settings1, settings2)

    def test_default_settings(self):
        """Test default settings are correctly initialized"""
        settings = WhatsAppAutomationSettings()
        
        self.assertEqual(settings.preferred_backend, "auto")
        self.assertEqual(settings.browser, "edge")
        self.assertEqual(settings.browser_profile, "Default")
        self.assertTrue(settings.fallback_enabled)
        self.assertTrue(settings.retry_enabled)
        self.assertEqual(settings.max_retries, 2)

    def test_backend_setter_validation(self):
        """Test backend setter validates input"""
        settings = WhatsAppAutomationSettings()
        
        # Valid values
        settings.preferred_backend = "auto"
        self.assertEqual(settings.preferred_backend, "auto")
        
        settings.preferred_backend = "desktop"
        self.assertEqual(settings.preferred_backend, "desktop")
        
        settings.preferred_backend = "web"
        self.assertEqual(settings.preferred_backend, "web")
        
        # Invalid value
        with self.assertRaises(ValueError):
            settings.preferred_backend = "invalid"

    def test_browser_setter_validation(self):
        """Test browser setter validates input"""
        settings = WhatsAppAutomationSettings()
        
        # Valid values
        for browser in ["edge", "chrome", "brave"]:
            settings.browser = browser
            self.assertEqual(settings.browser, browser)
        
        # Invalid value
        with self.assertRaises(ValueError):
            settings.browser = "firefox"

    def test_timeout_validation(self):
        """Test timeout setters validate ranges"""
        settings = WhatsAppAutomationSettings()
        
        # Valid desktop_launch_timeout
        settings.desktop_launch_timeout = 10
        self.assertEqual(settings.desktop_launch_timeout, 10)
        
        # Invalid (too low)
        with self.assertRaises(ValueError):
            settings.desktop_launch_timeout = 0
        
        # Invalid (too high)
        with self.assertRaises(ValueError):
            settings.desktop_launch_timeout = 100

    def test_retry_configuration(self):
        """Test retry configuration settings"""
        settings = WhatsAppAutomationSettings()
        
        # Test max_retries validation
        settings.max_retries = 3
        self.assertEqual(settings.max_retries, 3)
        
        with self.assertRaises(ValueError):
            settings.max_retries = 10  # Too high
        
        # Test retry_delay validation
        settings.retry_delay = 5
        self.assertEqual(settings.retry_delay, 5)
        
        with self.assertRaises(ValueError):
            settings.retry_delay = 50  # Too high
        
        # Test backoff multiplier
        settings.retry_backoff_multiplier = 2.5
        self.assertEqual(settings.retry_backoff_multiplier, 2.5)
        
        with self.assertRaises(ValueError):
            settings.retry_backoff_multiplier = 10.0  # Too high

    def test_message_configuration(self):
        """Test message configuration settings"""
        settings = WhatsAppAutomationSettings()
        
        # Test typing_interval
        settings.typing_interval = 0.1
        self.assertEqual(settings.typing_interval, 0.1)
        
        with self.assertRaises(ValueError):
            settings.typing_interval = 2.0  # Too high
        
        # Test message_max_length
        settings.message_max_length = 1000
        self.assertEqual(settings.message_max_length, 1000)
        
        with self.assertRaises(ValueError):
            settings.message_max_length = 20000  # Too high
        
        # Test allow_empty_messages
        settings.allow_empty_messages = True
        self.assertTrue(settings.allow_empty_messages)

    def test_debug_settings(self):
        """Test debug configuration"""
        settings = WhatsAppAutomationSettings()
        
        settings.debug_mode = True
        self.assertTrue(settings.debug_mode)
        
        settings.verbose_logging = True
        self.assertTrue(settings.verbose_logging)

    def test_get_all_settings(self):
        """Test getting all settings as dict"""
        settings = WhatsAppAutomationSettings()
        all_settings = settings.get_all_settings()
        
        self.assertIsInstance(all_settings, dict)
        self.assertIn("preferred_backend", all_settings)
        self.assertIn("browser", all_settings)
        self.assertIn("max_retries", all_settings)

    def test_update_settings(self):
        """Test bulk update of settings"""
        settings = WhatsAppAutomationSettings()
        
        updates = {
            "debug_mode": True,
            "max_retries": 3,
            "browser": "chrome"
        }
        
        settings.update_settings(updates)
        
        self.assertTrue(settings.debug_mode)
        self.assertEqual(settings.max_retries, 3)
        self.assertEqual(settings.browser, "chrome")

    def test_get_settings_function(self):
        """Test the get_settings() helper function"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        self.assertIs(settings1, settings2)
        self.assertIsInstance(settings1, WhatsAppAutomationSettings)

    def test_repr(self):
        """Test string representation"""
        settings = WhatsAppAutomationSettings()
        repr_str = repr(settings)
        
        self.assertIn("WhatsAppAutomationSettings", repr_str)
        self.assertIn("backend=", repr_str)
        self.assertIn("browser=", repr_str)


class TestWhatsAppSettingsPersistence(unittest.TestCase):
    """Test cases for settings file persistence"""

    def setUp(self):
        """Set up test environment with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_file = os.path.join(self.temp_dir, "whatsapp_settings.json")

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_settings_file_structure(self):
        """Test that settings file has correct structure"""
        settings = WhatsAppAutomationSettings()
        
        # Manually save to test file
        with open(self.test_config_file, 'w', encoding='utf-8') as f:
            json.dump(settings.get_all_settings(), f, indent=2)
        
        # Load and verify
        with open(self.test_config_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        
        required_keys = [
            "preferred_backend", "browser", "max_retries",
            "retry_enabled", "fallback_enabled"
        ]
        
        for key in required_keys:
            self.assertIn(key, loaded)


if __name__ == "__main__":
    unittest.main()
