import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from BACKEND.automations.network.network_config import NetworkAutomationConfig, NetworkAutomationSettings, get_network_settings
from BACKEND.automations.network.network_service import get_public_ip, check_internet_speed, clear_network_cache


class NetworkConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config(self):
        cfg = NetworkAutomationConfig()
        self.assertEqual(cfg.ip_check_timeout, 5)
        self.assertEqual(cfg.speed_test_timeout, 60)
        self.assertTrue(cfg.enable_ip_cache)
        self.assertTrue(cfg.enable_speed_cache)
        self.assertEqual(cfg.max_retries, 2)
        self.assertFalse(cfg.debug)
        self.assertTrue(len(cfg.ip_providers) > 0)

    def test_settings_singleton(self):
        s1 = get_network_settings()
        s2 = get_network_settings()
        self.assertIs(s1, s2)

    def test_cache_settings(self):
        with patch.object(NetworkAutomationSettings, "_load"):
            with patch.object(NetworkAutomationSettings, "save"):
                settings = NetworkAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                settings.set_ip_cache(False, 120)
                self.assertFalse(settings.config.enable_ip_cache)
                self.assertEqual(settings.config.ip_cache_duration, 120)
                
                settings.set_speed_cache(True, 300)
                self.assertTrue(settings.config.enable_speed_cache)
                self.assertEqual(settings.config.speed_cache_duration, 300)

    def test_timeout_settings(self):
        with patch.object(NetworkAutomationSettings, "_load"):
            with patch.object(NetworkAutomationSettings, "save"):
                settings = NetworkAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                settings.set_timeouts(ip_timeout=10, speed_timeout=90)
                self.assertEqual(settings.config.ip_check_timeout, 10)
                self.assertEqual(settings.config.speed_test_timeout, 90)

    def test_retry_settings(self):
        with patch.object(NetworkAutomationSettings, "_load"):
            with patch.object(NetworkAutomationSettings, "save"):
                settings = NetworkAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                settings.set_retries(5, 2)
                self.assertEqual(settings.config.max_retries, 5)
                self.assertEqual(settings.config.retry_delay, 2)

    def test_settings_persist_to_json(self):
        config_file = self.temp_path / "network_prefs.json"
        
        with patch("BACKEND.automations.network.network_config.CONFIG_FILE", config_file):
            with patch.object(NetworkAutomationSettings, "_load"):
                settings = NetworkAutomationSettings()
                settings._initialized = False
                settings.__init__()
                settings.config.enable_ip_cache = False
                settings.config.debug = True
                settings.save()
                
                self.assertTrue(config_file.exists())
                with open(config_file) as f:
                    data = json.load(f)
                    self.assertFalse(data["enable_ip_cache"])
                    self.assertTrue(data["debug"])


class NetworkServiceTest(unittest.TestCase):
    def setUp(self):
        clear_network_cache()
        
    def tearDown(self):
        clear_network_cache()

    def test_get_public_ip_with_cache(self):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = "203.0.113.42"
        
        with patch("requests.get", return_value=mock_response):
            with patch.object(NetworkAutomationSettings, "_load"):
                settings = NetworkAutomationSettings()
                settings._initialized = False
                settings.__init__()
                settings.config.enable_ip_cache = True
                settings.config.ip_cache_duration = 60
                
                # First call should hit the API
                result1 = get_public_ip()
                self.assertIn("203.0.113.42", result1)
                
                # Second call should use cache (no new request)
                with patch("requests.get") as mock_get:
                    result2 = get_public_ip()
                    self.assertEqual(result1, result2)
                    mock_get.assert_not_called()

    def test_get_public_ip_retry_on_failure(self):
        # Create proper mock responses
        mock_resp = MagicMock()
        mock_resp.text = "198.51.100.5  "
        
        with patch("requests.get", side_effect=[Exception("Network error"), mock_resp]):
            with patch.object(NetworkAutomationSettings, "_load"):
                settings = NetworkAutomationSettings()
                settings._initialized = False
                settings.__init__()
                settings.config.enable_ip_cache = False
                settings.config.max_retries = 0
                
                result = get_public_ip()
                self.assertIn("198.51.100.5", result)

    @patch("BACKEND.automations.network.network_service.speedtest")
    def test_check_internet_speed_with_cache(self, mock_speedtest_module):
        # Mock the entire speedtest module
        mock_st_instance = MagicMock()
        mock_st_instance.download.return_value = 100_000_000
        mock_st_instance.upload.return_value = 50_000_000
        mock_st_instance.results.ping = 15
        mock_speedtest_module.Speedtest.return_value = mock_st_instance
        
        with patch.object(NetworkAutomationSettings, "_load"):
            settings = NetworkAutomationSettings()
            settings._initialized = False
            settings.__init__()
            settings.config.enable_speed_cache = True
            settings.config.speed_cache_duration = 60
            
            # First call
            result1 = check_internet_speed()
            self.assertIn("100.0", result1)
            self.assertIn("50.0", result1)
            self.assertIn("15", result1)
            
            # Second call uses cache
            call_count_before = mock_speedtest_module.Speedtest.call_count
            result2 = check_internet_speed()
            call_count_after = mock_speedtest_module.Speedtest.call_count
            self.assertEqual(result1, result2)
            self.assertEqual(call_count_before, call_count_after)

    @patch("BACKEND.automations.network.network_service.speedtest")
    def test_check_internet_speed_error_handling(self, mock_speedtest_module):
        mock_speedtest_module.Speedtest.side_effect = Exception("Connection error")
        result = check_internet_speed()
        self.assertIn("unable to check", result.lower())


if __name__ == "__main__":
    unittest.main()
