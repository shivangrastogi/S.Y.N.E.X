# BACKEND/automations/youtube/youtube_automation_config.py
"""
YouTube Automation Settings Module
Singleton pattern for centralized configuration with JSON persistence
"""

import json
import os
from typing import Literal, Optional


class YouTubeAutomationSettings:
    """
    Singleton settings manager for YouTube automation
    Provides centralized configuration with JSON persistence
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # File paths
        self._config_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "DATA", "config"
        )
        self._config_file = os.path.join(self._config_dir, "youtube_settings.json")

        # Default settings
        self._settings = {
            # Browser Configuration
            "browser": "brave",  # brave | edge | chrome
            "browser_profile": "Default",
            "browser_user_data_dir": "",
            "headless": False,

            # YouTube Preferences
            "default_quality": "auto",  # auto | 1080p | 720p | 480p | 360p
            "default_speed": 1.0,  # 0.25 to 2.0
            "default_volume": 0.7,  # 0.0 to 1.0
            "auto_play": True,
            "auto_fullscreen": False,
            "auto_theater_mode": False,
            "auto_captions": False,

            # Search Configuration
            "search_timeout": 20,  # seconds
            "max_search_results": 10,
            "filter_shorts": False,
            "filter_live": False,
            "prefer_official": True,  # Prefer official/verified channels

            # Player Configuration
            "player_load_timeout": 15,  # seconds
            "player_ready_timeout": 10,  # seconds
            "video_element_timeout": 5,  # seconds
            "seek_step_seconds": 10,
            "volume_step": 0.1,  # 0.0 to 1.0
            "speed_step": 0.25,

            # Retry Configuration
            "retry_enabled": True,
            "max_retries": 2,
            "retry_delay": 3,  # seconds
            "retry_backoff_multiplier": 2.0,

            # Session Management
            "reuse_session": True,
            "session_timeout": 3600,  # seconds (1 hour)
            "auto_close_on_error": False,
            "recreate_on_crash": True,

            # Query Parsing
            "query_min_length": 1,
            "query_max_length": 200,
            "normalize_queries": True,
            "remove_noise_words": True,
            "noise_words": ["play", "youtube", "on youtube", "search"],

            # Advanced Features
            "enable_history": False,
            "history_file": "youtube_history.json",
            "enable_queue": False,
            "queue_max_size": 50,
            "enable_recommendations": False,

            # Performance
            "lazy_load_player": True,
            "cache_session": True,
            "parallel_operations": False,

            # Safety & Timeouts
            "global_timeout": 120,  # seconds
            "page_load_timeout": 15,  # seconds
            "script_timeout": 10,  # seconds

            # Error Handling
            "screenshot_on_error": False,
            "save_failed_queries": True,
            "failed_queries_file": "failed_youtube_queries.json",
            "fallback_to_native": True,  # Fallback to browser open if Selenium fails

            # Debugging
            "debug_mode": False,
            "verbose_logging": False,
            "log_search_queries": False,
            "log_player_actions": False,

            # Hinglish/Multi-language Support
            "support_hinglish": True,
            "support_unicode": True,
        }

        # Load from file if exists
        self.load_from_file()
        self._initialized = True

    # ==================================================
    # FILE PERSISTENCE
    # ==================================================

    def load_from_file(self):
        """Load settings from JSON file"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    self._settings.update(loaded_settings)
                if self.debug_mode:
                    print(f"✅ YouTube settings loaded from {self._config_file}")
            except Exception as e:
                print(f"⚠️ Failed to load YouTube settings: {e}")
                print("Using default settings")

    def save_to_file(self):
        """Save settings to JSON file"""
        try:
            os.makedirs(self._config_dir, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            if self.debug_mode:
                print(f"💾 YouTube settings saved to {self._config_file}")
        except Exception as e:
            print(f"❌ Failed to save YouTube settings: {e}")

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.__init__.__wrapped__(self)
        self.save_to_file()
        print("🔄 YouTube settings reset to defaults")

    # ==================================================
    # BROWSER CONFIGURATION
    # ==================================================

    @property
    def browser(self) -> str:
        return self._settings["browser"]

    @browser.setter
    def browser(self, value: Literal["brave", "edge", "chrome"]):
        if value not in ["brave", "edge", "chrome"]:
            raise ValueError("browser must be 'brave', 'edge', or 'chrome'")
        self._settings["browser"] = value
        self.save_to_file()

    @property
    def browser_profile(self) -> str:
        return self._settings["browser_profile"]

    @browser_profile.setter
    def browser_profile(self, value: str):
        self._settings["browser_profile"] = str(value)
        self.save_to_file()

    @property
    def headless(self) -> bool:
        return self._settings["headless"]

    @headless.setter
    def headless(self, value: bool):
        self._settings["headless"] = bool(value)
        self.save_to_file()

    # ==================================================
    # YOUTUBE PREFERENCES
    # ==================================================

    @property
    def default_quality(self) -> str:
        return self._settings["default_quality"]

    @default_quality.setter
    def default_quality(self, value: str):
        valid_qualities = ["auto", "1080p", "720p", "480p", "360p", "240p", "144p"]
        if value not in valid_qualities:
            raise ValueError(f"default_quality must be one of {valid_qualities}")
        self._settings["default_quality"] = value
        self.save_to_file()

    @property
    def default_speed(self) -> float:
        return self._settings["default_speed"]

    @default_speed.setter
    def default_speed(self, value: float):
        if value < 0.25 or value > 2.0:
            raise ValueError("default_speed must be between 0.25-2.0")
        self._settings["default_speed"] = float(value)
        self.save_to_file()

    @property
    def default_volume(self) -> float:
        return self._settings["default_volume"]

    @default_volume.setter
    def default_volume(self, value: float):
        if value < 0.0 or value > 1.0:
            raise ValueError("default_volume must be between 0.0-1.0")
        self._settings["default_volume"] = float(value)
        self.save_to_file()

    @property
    def auto_play(self) -> bool:
        return self._settings["auto_play"]

    @auto_play.setter
    def auto_play(self, value: bool):
        self._settings["auto_play"] = bool(value)
        self.save_to_file()

    # ==================================================
    # TIMEOUT CONFIGURATION
    # ==================================================

    @property
    def search_timeout(self) -> int:
        return self._settings["search_timeout"]

    @search_timeout.setter
    def search_timeout(self, value: int):
        if value < 5 or value > 60:
            raise ValueError("search_timeout must be between 5-60 seconds")
        self._settings["search_timeout"] = int(value)
        self.save_to_file()

    @property
    def player_load_timeout(self) -> int:
        return self._settings["player_load_timeout"]

    @player_load_timeout.setter
    def player_load_timeout(self, value: int):
        if value < 5 or value > 60:
            raise ValueError("player_load_timeout must be between 5-60 seconds")
        self._settings["player_load_timeout"] = int(value)
        self.save_to_file()

    @property
    def page_load_timeout(self) -> int:
        return self._settings["page_load_timeout"]

    @page_load_timeout.setter
    def page_load_timeout(self, value: int):
        if value < 5 or value > 60:
            raise ValueError("page_load_timeout must be between 5-60 seconds")
        self._settings["page_load_timeout"] = int(value)
        self.save_to_file()

    # ==================================================
    # RETRY CONFIGURATION
    # ==================================================

    @property
    def retry_enabled(self) -> bool:
        return self._settings["retry_enabled"]

    @retry_enabled.setter
    def retry_enabled(self, value: bool):
        self._settings["retry_enabled"] = bool(value)
        self.save_to_file()

    @property
    def max_retries(self) -> int:
        return self._settings["max_retries"]

    @max_retries.setter
    def max_retries(self, value: int):
        if value < 0 or value > 5:
            raise ValueError("max_retries must be between 0-5")
        self._settings["max_retries"] = int(value)
        self.save_to_file()

    @property
    def retry_delay(self) -> int:
        return self._settings["retry_delay"]

    @retry_delay.setter
    def retry_delay(self, value: int):
        if value < 1 or value > 30:
            raise ValueError("retry_delay must be between 1-30 seconds")
        self._settings["retry_delay"] = int(value)
        self.save_to_file()

    # ==================================================
    # PLAYER CONFIGURATION
    # ==================================================

    @property
    def seek_step_seconds(self) -> int:
        return self._settings["seek_step_seconds"]

    @seek_step_seconds.setter
    def seek_step_seconds(self, value: int):
        if value < 1 or value > 60:
            raise ValueError("seek_step_seconds must be between 1-60 seconds")
        self._settings["seek_step_seconds"] = int(value)
        self.save_to_file()

    @property
    def volume_step(self) -> float:
        return self._settings["volume_step"]

    @volume_step.setter
    def volume_step(self, value: float):
        if value < 0.01 or value > 0.5:
            raise ValueError("volume_step must be between 0.01-0.5")
        self._settings["volume_step"] = float(value)
        self.save_to_file()

    @property
    def speed_step(self) -> float:
        return self._settings["speed_step"]

    @speed_step.setter
    def speed_step(self, value: float):
        if value < 0.1 or value > 1.0:
            raise ValueError("speed_step must be between 0.1-1.0")
        self._settings["speed_step"] = float(value)
        self.save_to_file()

    # ==================================================
    # DEBUGGING
    # ==================================================

    @property
    def debug_mode(self) -> bool:
        return self._settings["debug_mode"]

    @debug_mode.setter
    def debug_mode(self, value: bool):
        self._settings["debug_mode"] = bool(value)
        self.save_to_file()

    @property
    def verbose_logging(self) -> bool:
        return self._settings["verbose_logging"]

    @verbose_logging.setter
    def verbose_logging(self, value: bool):
        self._settings["verbose_logging"] = bool(value)
        self.save_to_file()

    # ==================================================
    # UTILITY METHODS
    # ==================================================

    def get_all_settings(self) -> dict:
        """Get a copy of all current settings"""
        return self._settings.copy()

    def update_settings(self, settings_dict: dict):
        """Update multiple settings at once"""
        self._settings.update(settings_dict)
        self.save_to_file()

    def __repr__(self):
        return f"<YouTubeAutomationSettings browser={self.browser} quality={self.default_quality}>"


# ==================================================
# SINGLETON INSTANCE
# ==================================================

def get_settings() -> YouTubeAutomationSettings:
    """Get the singleton settings instance"""
    return YouTubeAutomationSettings()
