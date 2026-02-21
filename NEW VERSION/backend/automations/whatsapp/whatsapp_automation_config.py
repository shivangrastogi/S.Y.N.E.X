# BACKEND/automations/whatsapp/whatsapp_automation_config.py
"""
WhatsApp Automation Settings Module
Singleton pattern for centralized configuration with JSON persistence
"""

import json
import os
from datetime import datetime, timedelta
from typing import Literal, Optional


class WhatsAppAutomationSettings:
    """
    Singleton settings manager for WhatsApp automation
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
        self._config_file = os.path.join(self._config_dir, "whatsapp_settings.json")

        # Default settings
        self._settings = {
            # Backend Configuration
            "preferred_backend": "auto",  # auto | desktop | web
            "fallback_enabled": True,
            "auto_detect_desktop": True,

            # Browser Configuration (for WhatsApp Web)
            "browser": "edge",  # edge | chrome | brave
            "browser_profile": "Default",
            "browser_user_data_dir": "",  # Empty = use default

            # Desktop Configuration
            "desktop_launch_timeout": 10,  # seconds
            "desktop_ready_timeout": 40,  # seconds
            "desktop_launch_methods": ["direct", "uri", "explorer"],

            # Web Configuration
            "web_load_delay": 15,  # seconds
            "web_ready_timeout": 30,  # seconds
            "web_qr_scan_timeout": 120,  # seconds

            # Message Configuration
            "typing_interval": 0.05,  # seconds between keystrokes
            "send_delay": 0.5,  # seconds before sending
            "message_max_length": 5000,  # characters
            "allow_empty_messages": False,

            # Retry Configuration
            "retry_enabled": True,
            "max_retries": 2,
            "retry_delay": 3,  # seconds
            "retry_backoff_multiplier": 2.0,

            # Contact Management
            "contact_validation_enabled": True,
            "contact_min_length": 1,
            "contact_max_length": 100,
            "normalize_contact_names": True,

            # Window Management
            "bring_window_to_front": True,
            "minimize_after_send": False,
            "close_after_send": False,

            # Safety & Timeouts
            "ui_prime_delay": 0.3,  # seconds
            "search_clear_delay": 0.3,  # seconds
            "chat_open_delay": 1.2,  # seconds
            "global_timeout": 120,  # seconds

            # Advanced Features
            "enable_message_queue": False,
            "queue_max_size": 50,
            "enable_scheduling": False,
            "enable_attachments": False,

            # Debugging
            "debug_mode": False,
            "verbose_logging": False,
            "screenshot_on_error": False,
            "log_pyautogui_actions": False,

            # Cache Configuration
            "cache_contact_searches": False,
            "contact_cache_duration": 300,  # seconds (5 min)

            # Error Handling
            "screenshot_on_failure": False,
            "save_failed_messages": True,
            "failed_messages_file": "failed_whatsapp_messages.json",

            # Performance
            "parallel_message_sending": False,
            "max_parallel_messages": 3,

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
                    print(f"✅ WhatsApp settings loaded from {self._config_file}")
            except Exception as e:
                print(f"⚠️ Failed to load WhatsApp settings: {e}")
                print("Using default settings")

    def save_to_file(self):
        """Save settings to JSON file"""
        try:
            os.makedirs(self._config_dir, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            if self.debug_mode:
                print(f"💾 WhatsApp settings saved to {self._config_file}")
        except Exception as e:
            print(f"❌ Failed to save WhatsApp settings: {e}")

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.__init__.__wrapped__(self)
        self.save_to_file()
        print("🔄 WhatsApp settings reset to defaults")

    # ==================================================
    # BACKEND CONFIGURATION
    # ==================================================

    @property
    def preferred_backend(self) -> str:
        return self._settings["preferred_backend"]

    @preferred_backend.setter
    def preferred_backend(self, value: Literal["auto", "desktop", "web"]):
        if value not in ["auto", "desktop", "web"]:
            raise ValueError("preferred_backend must be 'auto', 'desktop', or 'web'")
        self._settings["preferred_backend"] = value
        self.save_to_file()

    @property
    def fallback_enabled(self) -> bool:
        return self._settings["fallback_enabled"]

    @fallback_enabled.setter
    def fallback_enabled(self, value: bool):
        self._settings["fallback_enabled"] = bool(value)
        self.save_to_file()

    @property
    def auto_detect_desktop(self) -> bool:
        return self._settings["auto_detect_desktop"]

    @auto_detect_desktop.setter
    def auto_detect_desktop(self, value: bool):
        self._settings["auto_detect_desktop"] = bool(value)
        self.save_to_file()

    # ==================================================
    # BROWSER CONFIGURATION
    # ==================================================

    @property
    def browser(self) -> str:
        return self._settings["browser"]

    @browser.setter
    def browser(self, value: Literal["edge", "chrome", "brave"]):
        if value not in ["edge", "chrome", "brave"]:
            raise ValueError("browser must be 'edge', 'chrome', or 'brave'")
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
    def browser_user_data_dir(self) -> str:
        return self._settings["browser_user_data_dir"]

    @browser_user_data_dir.setter
    def browser_user_data_dir(self, value: str):
        self._settings["browser_user_data_dir"] = str(value)
        self.save_to_file()

    # ==================================================
    # TIMEOUT CONFIGURATION
    # ==================================================

    @property
    def desktop_launch_timeout(self) -> int:
        return self._settings["desktop_launch_timeout"]

    @desktop_launch_timeout.setter
    def desktop_launch_timeout(self, value: int):
        if value < 1 or value > 60:
            raise ValueError("desktop_launch_timeout must be between 1-60 seconds")
        self._settings["desktop_launch_timeout"] = int(value)
        self.save_to_file()

    @property
    def desktop_ready_timeout(self) -> int:
        return self._settings["desktop_ready_timeout"]

    @desktop_ready_timeout.setter
    def desktop_ready_timeout(self, value: int):
        if value < 5 or value > 120:
            raise ValueError("desktop_ready_timeout must be between 5-120 seconds")
        self._settings["desktop_ready_timeout"] = int(value)
        self.save_to_file()

    @property
    def web_load_delay(self) -> int:
        return self._settings["web_load_delay"]

    @web_load_delay.setter
    def web_load_delay(self, value: int):
        if value < 5 or value > 60:
            raise ValueError("web_load_delay must be between 5-60 seconds")
        self._settings["web_load_delay"] = int(value)
        self.save_to_file()

    @property
    def web_ready_timeout(self) -> int:
        return self._settings["web_ready_timeout"]

    @web_ready_timeout.setter
    def web_ready_timeout(self, value: int):
        if value < 5 or value > 120:
            raise ValueError("web_ready_timeout must be between 5-120 seconds")
        self._settings["web_ready_timeout"] = int(value)
        self.save_to_file()

    @property
    def web_qr_scan_timeout(self) -> int:
        return self._settings["web_qr_scan_timeout"]

    @web_qr_scan_timeout.setter
    def web_qr_scan_timeout(self, value: int):
        if value < 30 or value > 300:
            raise ValueError("web_qr_scan_timeout must be between 30-300 seconds")
        self._settings["web_qr_scan_timeout"] = int(value)
        self.save_to_file()

    # ==================================================
    # MESSAGE CONFIGURATION
    # ==================================================

    @property
    def typing_interval(self) -> float:
        return self._settings["typing_interval"]

    @typing_interval.setter
    def typing_interval(self, value: float):
        if value < 0.01 or value > 1.0:
            raise ValueError("typing_interval must be between 0.01-1.0 seconds")
        self._settings["typing_interval"] = float(value)
        self.save_to_file()

    @property
    def message_max_length(self) -> int:
        return self._settings["message_max_length"]

    @message_max_length.setter
    def message_max_length(self, value: int):
        if value < 1 or value > 10000:
            raise ValueError("message_max_length must be between 1-10000 characters")
        self._settings["message_max_length"] = int(value)
        self.save_to_file()

    @property
    def allow_empty_messages(self) -> bool:
        return self._settings["allow_empty_messages"]

    @allow_empty_messages.setter
    def allow_empty_messages(self, value: bool):
        self._settings["allow_empty_messages"] = bool(value)
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

    @property
    def retry_backoff_multiplier(self) -> float:
        return self._settings["retry_backoff_multiplier"]

    @retry_backoff_multiplier.setter
    def retry_backoff_multiplier(self, value: float):
        if value < 1.0 or value > 5.0:
            raise ValueError("retry_backoff_multiplier must be between 1.0-5.0")
        self._settings["retry_backoff_multiplier"] = float(value)
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
        return f"<WhatsAppAutomationSettings backend={self.preferred_backend} browser={self.browser}>"


# ==================================================
# SINGLETON INSTANCE
# ==================================================

def get_settings() -> WhatsAppAutomationSettings:
    """Get the singleton settings instance"""
    return WhatsAppAutomationSettings()
