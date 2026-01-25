"""
Google automation settings and preferences.
Controls whether to prefer native (keystroke-based) or Selenium automation.
"""
import os
import json
from dataclasses import dataclass, asdict
from pathlib import Path


CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_FILE = CONFIG_DIR / "google_prefs.json"


@dataclass
class GoogleAutomationConfig:
    """Settings for Google automation behavior."""
    
    # Prefer native keystrokes over Selenium for search, navigation, tabs, and scrolling
    prefer_native: bool = True
    
    # Only use native if a browser is already open; never spawn one
    native_only_if_open: bool = True
    
    # Fallback to Selenium when native fails
    allow_selenium_fallback: bool = True
    
    # Additional debug logging
    debug: bool = False


class GoogleAutomationSettings:
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
        self.config = GoogleAutomationConfig()
        self._load()
    
    def _load(self):
        """Load settings from disk, or use defaults if not found."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.config = GoogleAutomationConfig(**data)
                    if self.config.debug:
                        print(f"[Google Config] Loaded from {CONFIG_FILE}")
        except Exception as e:
            if self.config.debug:
                print(f"[Google Config] Failed to load: {e}. Using defaults.")
            self.config = GoogleAutomationConfig()
    
    def save(self):
        """Persist settings to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(asdict(self.config), f, indent=2)
                if self.config.debug:
                    print(f"[Google Config] Saved to {CONFIG_FILE}")
        except Exception as e:
            if self.config.debug:
                print(f"[Google Config] Failed to save: {e}")
    
    def set_prefer_native(self, value: bool):
        """Enable/disable native automation preference."""
        self.config.prefer_native = value
        self.save()
    
    def set_native_only_if_open(self, value: bool):
        """Set whether to use native only if browser is already open."""
        self.config.native_only_if_open = value
        self.save()
    
    def set_allow_selenium_fallback(self, value: bool):
        """Enable/disable Selenium fallback when native fails."""
        self.config.allow_selenium_fallback = value
        self.save()
    
    def set_debug(self, value: bool):
        """Enable/disable debug logging."""
        self.config.debug = value
        self.save()
    
    def get_config(self) -> GoogleAutomationConfig:
        """Get current configuration."""
        return self.config
    
    def reset_to_defaults(self):
        """Reset to default settings."""
        self.config = GoogleAutomationConfig()
        self.save()
        if self.config.debug:
            print("[Google Config] Reset to defaults")


def get_settings() -> GoogleAutomationSettings:
    """Singleton accessor for Google automation settings."""
    return GoogleAutomationSettings()
