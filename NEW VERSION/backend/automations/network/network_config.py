"""
Network automation settings and preferences.
Controls timeouts, caching, retry behavior, and API endpoints.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path


CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_FILE = CONFIG_DIR / "network_prefs.json"


@dataclass
class NetworkAutomationConfig:
    """Settings for network automation behavior."""
    
    # Request timeouts in seconds
    ip_check_timeout: int = 5
    speed_test_timeout: int = 60
    
    # Cache results to avoid hammering APIs
    enable_ip_cache: bool = True
    ip_cache_duration: int = 300  # seconds
    
    enable_speed_cache: bool = True
    speed_cache_duration: int = 600  # seconds
    
    # Retry behavior
    max_retries: int = 2
    retry_delay: int = 1
    
    # API endpoints for IP checking
    ip_providers: list = None
    
    # Enable debug logging
    debug: bool = False
    
    def __post_init__(self):
        if self.ip_providers is None:
            self.ip_providers = [
                "https://api.ipify.org",
                "https://api.my-ip.io/ip",
                "https://icanhazip.com"
            ]


class NetworkAutomationSettings:
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
        self.config = NetworkAutomationConfig()
        self._load()
    
    def _load(self):
        """Load settings from disk, or use defaults if not found."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.config = NetworkAutomationConfig(**data)
                    if self.config.debug:
                        print(f"[Network Config] Loaded from {CONFIG_FILE}")
        except Exception as e:
            if self.config.debug:
                print(f"[Network Config] Failed to load: {e}. Using defaults.")
            self.config = NetworkAutomationConfig()
    
    def save(self):
        """Persist settings to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(asdict(self.config), f, indent=2)
                if self.config.debug:
                    print(f"[Network Config] Saved to {CONFIG_FILE}")
        except Exception as e:
            if self.config.debug:
                print(f"[Network Config] Failed to save: {e}")
    
    def set_ip_cache(self, enabled: bool, duration: int = None):
        """Enable/disable IP address caching."""
        self.config.enable_ip_cache = enabled
        if duration is not None:
            self.config.ip_cache_duration = max(10, duration)
        self.save()
    
    def set_speed_cache(self, enabled: bool, duration: int = None):
        """Enable/disable speed test result caching."""
        self.config.enable_speed_cache = enabled
        if duration is not None:
            self.config.speed_cache_duration = max(10, duration)
        self.save()
    
    def set_timeouts(self, ip_timeout: int = None, speed_timeout: int = None):
        """Set request timeouts."""
        if ip_timeout is not None:
            self.config.ip_check_timeout = max(1, ip_timeout)
        if speed_timeout is not None:
            self.config.speed_test_timeout = max(10, speed_timeout)
        self.save()
    
    def set_retries(self, max_retries: int, delay: int = None):
        """Set retry behavior."""
        self.config.max_retries = max(0, max_retries)
        if delay is not None:
            self.config.retry_delay = max(0, delay)
        self.save()
    
    def set_debug(self, value: bool):
        """Enable/disable debug logging."""
        self.config.debug = value
        self.save()
    
    def get_config(self) -> NetworkAutomationConfig:
        """Get current configuration."""
        return self.config
    
    def reset_to_defaults(self):
        """Reset to default settings."""
        self.config = NetworkAutomationConfig()
        self.save()
        if self.config.debug:
            print("[Network Config] Reset to defaults")


def get_network_settings() -> NetworkAutomationSettings:
    """Singleton accessor for network automation settings."""
    return NetworkAutomationSettings()
