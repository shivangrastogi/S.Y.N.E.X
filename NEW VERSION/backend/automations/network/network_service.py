# BACKEND/automations/network/network_service.py
import random
import time
import requests
import speedtest
from datetime import datetime, timedelta

from BACKEND.automations.network.responses import WAIT_RESPONSES
from BACKEND.automations.network.network_config import get_network_settings


# Cache storage
_ip_cache = {"value": None, "expires_at": None}
_speed_cache = {"value": None, "expires_at": None}


def _safe_speak(speech, message: str):
    if speech and message:
        try:
            speech.speak(message)
        except Exception:
            pass


def _is_cache_valid(cache_dict) -> bool:
    """Check if cached value is still valid."""
    if cache_dict["value"] is None or cache_dict["expires_at"] is None:
        return False
    return datetime.now() < cache_dict["expires_at"]


def get_public_ip():
    """Fetch public IP address with caching and retry support."""
    settings = get_network_settings()
    cfg = settings.get_config()
    
    # Check cache first
    if cfg.enable_ip_cache and _is_cache_valid(_ip_cache):
        if cfg.debug:
            print("[Network] Returning cached IP address")
        return _ip_cache["value"]
    
    # Try multiple providers with retries
    for attempt in range(cfg.max_retries + 1):
        for provider in cfg.ip_providers:
            try:
                if cfg.debug:
                    print(f"[Network] Fetching IP from {provider} (attempt {attempt + 1})")
                response = requests.get(provider, timeout=cfg.ip_check_timeout)
                ip = response.text.strip()
                
                if ip:
                    result = f"Your public IP address is {ip}."
                    
                    # Cache the result
                    if cfg.enable_ip_cache:
                        _ip_cache["value"] = result
                        _ip_cache["expires_at"] = datetime.now() + timedelta(seconds=cfg.ip_cache_duration)
                    
                    return result
            except Exception as e:
                if cfg.debug:
                    print(f"[Network] IP check failed for {provider}: {e}")
                continue
        
        # Wait before retry
        if attempt < cfg.max_retries:
            time.sleep(cfg.retry_delay)
    
    return "Sorry, I could not fetch your IP address right now."


def check_internet_speed(speech=None):
    """Measure internet speed with caching and improved error handling."""
    settings = get_network_settings()
    cfg = settings.get_config()
    
    # Check cache first
    if cfg.enable_speed_cache and _is_cache_valid(_speed_cache):
        if cfg.debug:
            print("[Network] Returning cached speed test results")
        return _speed_cache["value"]
    
    try:
        if speech:
            _safe_speak(speech, random.choice(WAIT_RESPONSES))
            _safe_speak(speech, "Checking your internet speed. Please wait.")

        if cfg.debug:
            print("[Network] Starting speed test...")
        
        st = speedtest.Speedtest()
        st.get_best_server()

        download = st.download() / 1_000_000
        upload = st.upload() / 1_000_000
        ping = st.results.ping
        
        result = (
            f"Your internet speed is as follows. "
            f"Download speed is {download:.1f} megabits per second. "
            f"Upload speed is {upload:.1f} megabits per second. "
            f"Ping is {ping:.0f} milliseconds."
        )
        
        # Cache the result
        if cfg.enable_speed_cache:
            _speed_cache["value"] = result
            _speed_cache["expires_at"] = datetime.now() + timedelta(seconds=cfg.speed_cache_duration)
        
        if cfg.debug:
            print(f"[Network] Speed test complete: {download:.1f}/{upload:.1f} Mbps, {ping:.0f}ms")
        
        return result

    except Exception as e:
        if cfg.debug:
            print(f"[Network] Speed test failed: {e}")
        return (
            "Sorry, I was unable to check your internet speed. "
            "Please check your connection and try again."
        )


def clear_network_cache():
    """Clear all cached network results."""
    global _ip_cache, _speed_cache
    _ip_cache = {"value": None, "expires_at": None}
    _speed_cache = {"value": None, "expires_at": None}
