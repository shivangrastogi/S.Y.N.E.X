"""
Battery automation settings and preferences.
Controls whether continuous monitoring is enabled, polling intervals, and alerting thresholds.
"""
import os
import json
from dataclasses import dataclass, asdict
from pathlib import Path


CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_FILE = CONFIG_DIR / "battery_prefs.json"


@dataclass
class BatteryAutomationConfig:
    """Settings for battery automation behavior."""
    
    # Enable or disable continuous battery monitoring
    enable_monitoring: bool = True
    
    # Polling interval in seconds (higher = less CPU usage, slower alerts)
    monitor_interval: int = 60
    
    # Battery level thresholds
    critical_threshold: int = 10
    low_threshold: int = 30
    full_threshold: int = 100
    
    # Only announce alerts when system is idle (avoids interruption during work)
    idle_only: bool = True
    
    # Max pending alerts when system is busy
    max_pending_alerts: int = 5
    
    # Plug/unplug alert cooldown in seconds
    plug_cooldown: int = 180
    
    # Level alert cooldown in seconds
    level_cooldown: int = 300
    
    # Enable debug logging
    debug: bool = False


class BatteryAutomationSettings:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config = BatteryAutomationConfig()
        self._load()
    
    def _load(self):
        """Load settings from disk, or use defaults if not found."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.config = BatteryAutomationConfig(**data)
                    if self.config.debug:
                        print(f"[Battery Config] Loaded from {CONFIG_FILE}")
        except Exception as e:
            if self.config.debug:
                print(f"[Battery Config] Failed to load: {e}. Using defaults.")
            self.config = BatteryAutomationConfig()
    
    def save(self):
        """Persist settings to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(asdict(self.config), f, indent=2)
                if self.config.debug:
                    print(f"[Battery Config] Saved to {CONFIG_FILE}")
        except Exception as e:
            if self.config.debug:
                print(f"[Battery Config] Failed to save: {e}")
    
    def set_enable_monitoring(self, value: bool):
        """Enable or disable continuous battery monitoring."""
        self.config.enable_monitoring = value
        self.save()
    
    def set_monitor_interval(self, seconds: int):
        """Set polling interval in seconds (affects CPU usage)."""
        if seconds < 5:
            seconds = 5  # Minimum 5s to avoid CPU spinning
        self.config.monitor_interval = seconds
        self.save()
    
    def set_critical_threshold(self, percent: int):
        """Set critical battery level threshold."""
        self.config.critical_threshold = max(0, min(100, percent))
        self.save()
    
    def set_low_threshold(self, percent: int):
        """Set low battery level threshold."""
        self.config.low_threshold = max(0, min(100, percent))
        self.save()
    
    def set_idle_only(self, value: bool):
        """Set whether alerts only fire when idle."""
        self.config.idle_only = value
        self.save()
    
    def set_debug(self, value: bool):
        """Enable/disable debug logging."""
        self.config.debug = value
        self.save()
    
    def get_config(self) -> BatteryAutomationConfig:
        """Get current configuration."""
        return self.config
    
    def reset_to_defaults(self):
        """Reset to default settings."""
        self.config = BatteryAutomationConfig()
        self.save()
        if self.config.debug:
            print("[Battery Config] Reset to defaults")


def get_battery_settings() -> BatteryAutomationSettings:
    """Singleton accessor for battery automation settings."""
    return BatteryAutomationSettings()
