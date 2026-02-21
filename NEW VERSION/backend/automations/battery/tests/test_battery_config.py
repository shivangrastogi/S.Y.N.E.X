import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from BACKEND.automations.battery.battery_config import BatteryAutomationConfig, BatteryAutomationSettings, get_battery_settings


class BatteryConfigTest(unittest.TestCase):
    def setUp(self):
        # Use temp dir for test config
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config(self):
        cfg = BatteryAutomationConfig()
        self.assertTrue(cfg.enable_monitoring)
        self.assertEqual(cfg.monitor_interval, 60)
        self.assertEqual(cfg.critical_threshold, 10)
        self.assertEqual(cfg.low_threshold, 30)
        self.assertEqual(cfg.full_threshold, 100)
        self.assertTrue(cfg.idle_only)
        self.assertFalse(cfg.debug)

    def test_settings_singleton(self):
        s1 = get_battery_settings()
        s2 = get_battery_settings()
        self.assertIs(s1, s2)

    def test_enable_disable_monitoring(self):
        with patch.object(BatteryAutomationSettings, "_load"):
            with patch.object(BatteryAutomationSettings, "save"):
                settings = BatteryAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                self.assertTrue(settings.config.enable_monitoring)
                settings.set_enable_monitoring(False)
                self.assertFalse(settings.config.enable_monitoring)
                settings.set_enable_monitoring(True)
                self.assertTrue(settings.config.enable_monitoring)

    def test_monitor_interval(self):
        with patch.object(BatteryAutomationSettings, "_load"):
            with patch.object(BatteryAutomationSettings, "save"):
                settings = BatteryAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                settings.set_monitor_interval(120)
                self.assertEqual(settings.config.monitor_interval, 120)
                
                # Minimum 5 seconds
                settings.set_monitor_interval(2)
                self.assertEqual(settings.config.monitor_interval, 5)

    def test_thresholds(self):
        with patch.object(BatteryAutomationSettings, "_load"):
            with patch.object(BatteryAutomationSettings, "save"):
                settings = BatteryAutomationSettings()
                settings._initialized = False
                settings.__init__()
                
                settings.set_critical_threshold(15)
                self.assertEqual(settings.config.critical_threshold, 15)
                
                settings.set_low_threshold(35)
                self.assertEqual(settings.config.low_threshold, 35)

    def test_settings_persist_to_json(self):
        config_file = self.temp_path / "battery_prefs.json"
        
        with patch("BACKEND.automations.battery.battery_config.CONFIG_FILE", config_file):
            with patch.object(BatteryAutomationSettings, "_load"):
                settings = BatteryAutomationSettings()
                settings._initialized = False
                settings.__init__()
                settings.config.enable_monitoring = False
                settings.config.monitor_interval = 120
                settings.config.debug = True
                settings.save()
                
                # Check file was written
                self.assertTrue(config_file.exists())
                with open(config_file) as f:
                    data = json.load(f)
                    self.assertFalse(data["enable_monitoring"])
                    self.assertEqual(data["monitor_interval"], 120)
                    self.assertTrue(data["debug"])

    def test_settings_load_from_json(self):
        config_file = self.temp_path / "battery_prefs.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write test config
        test_cfg = {
            "enable_monitoring": False,
            "monitor_interval": 120,
            "critical_threshold": 15,
            "low_threshold": 35,
            "full_threshold": 100,
            "idle_only": False,
            "max_pending_alerts": 10,
            "plug_cooldown": 200,
            "level_cooldown": 400,
            "debug": True
        }
        with open(config_file, "w") as f:
            json.dump(test_cfg, f)
        
        with patch("BACKEND.automations.battery.battery_config.CONFIG_FILE", config_file):
            settings = BatteryAutomationSettings()
            settings._initialized = False
            settings.__init__()
            
            cfg = settings.get_config()
            self.assertFalse(cfg.enable_monitoring)
            self.assertEqual(cfg.monitor_interval, 120)
            self.assertEqual(cfg.critical_threshold, 15)
            self.assertEqual(cfg.low_threshold, 35)
            self.assertTrue(cfg.debug)


if __name__ == "__main__":
    unittest.main()
