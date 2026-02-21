import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from BACKEND.automations.google.google_config import GoogleAutomationConfig, GoogleAutomationSettings, get_settings


class GoogleConfigTest(unittest.TestCase):
    def setUp(self):
        # Use temp dir for test config
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config(self):
        cfg = GoogleAutomationConfig()
        self.assertTrue(cfg.prefer_native)
        self.assertTrue(cfg.native_only_if_open)
        self.assertTrue(cfg.allow_selenium_fallback)
        self.assertFalse(cfg.debug)

    def test_settings_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)

    def test_settings_mutators(self):
        with patch.object(GoogleAutomationSettings, "_load"):
            with patch.object(GoogleAutomationSettings, "save"):
                settings = GoogleAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                settings.set_prefer_native(False)
                self.assertFalse(settings.config.prefer_native)
                
                settings.set_debug(True)
                self.assertTrue(settings.config.debug)
                
                settings.reset_to_defaults()
                self.assertTrue(settings.config.prefer_native)
                self.assertFalse(settings.config.debug)

    def test_settings_persist_to_json(self):
        # Mock the config path
        config_file = self.temp_path / "google_prefs.json"
        
        with patch("BACKEND.automations.google.google_config.CONFIG_FILE", config_file):
            with patch.object(GoogleAutomationSettings, "_load"):
                settings = GoogleAutomationSettings()
                settings._initialized = False
                settings.__init__()
                settings.config.prefer_native = False
                settings.config.debug = True
                settings.save()
                
                # Check file was written
                self.assertTrue(config_file.exists())
                with open(config_file) as f:
                    data = json.load(f)
                    self.assertFalse(data["prefer_native"])
                    self.assertTrue(data["debug"])

    def test_settings_load_from_json(self):
        config_file = self.temp_path / "google_prefs.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write test config
        test_cfg = {
            "prefer_native": False,
            "native_only_if_open": False,
            "allow_selenium_fallback": True,
            "debug": True
        }
        with open(config_file, "w") as f:
            json.dump(test_cfg, f)
        
        with patch("BACKEND.automations.google.google_config.CONFIG_FILE", config_file):
            settings = GoogleAutomationSettings()
            settings._initialized = False
            settings.__init__()
            
            cfg = settings.get_config()
            self.assertFalse(cfg.prefer_native)
            self.assertFalse(cfg.native_only_if_open)
            self.assertTrue(cfg.allow_selenium_fallback)
            self.assertTrue(cfg.debug)


if __name__ == "__main__":
    unittest.main()
