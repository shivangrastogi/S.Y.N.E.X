# BACKEND/automations/whatsapp/browser_manager.py
"""
Enhanced browser manager with fallback mechanisms and retry logic
"""

import subprocess
import time
import os
import psutil

try:
    from BACKEND.automations.whatsapp.whatsapp_automation_config import get_settings
except ImportError:
    get_settings = None

from BACKEND.automations.whatsapp.window_utils import (
    find_whatsapp_tab,
    find_browser_window,
    bring_window_to_front
)

# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
WHATSAPP_URL = "https://web.whatsapp.com"


class BrowserManagerError(Exception):
    """Custom exception for browser manager errors"""
    pass


def is_browser_running(browser_name):
    """Check if browser process is running"""
    browser_name = browser_name.lower()

    # Map browser names to process names
    process_map = {
        "edge": ["msedge.exe"],
        "chrome": ["chrome.exe"],
        "brave": ["brave.exe"]
    }

    processes = process_map.get(browser_name, [])

    for proc in psutil.process_iter(['name']):
        try:
            proc_name = proc.info['name'].lower()
            for target in processes:
                if target in proc_name:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return False


def get_browser_path(browser_name: str) -> str:
    """Get browser executable path with fallback"""
    
    browser_paths = {
        "edge": [
            EDGE_PATH,
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ],
        "chrome": [
            CHROME_PATH,
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ],
        "brave": [
            BRAVE_PATH,
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"
        ]
    }
    
    paths = browser_paths.get(browser_name.lower(), [])
    
    for path in paths:
        if os.path.exists(path):
            return path
    
    return None


def open_whatsapp_web():
    """
    Smart WhatsApp Web launcher with fallback mechanisms and retry logic
    """
    
    settings = get_settings() if get_settings else None
    
    if settings and settings.debug_mode:
        print("🌐 Opening WhatsApp Web...")

    # Try to open WhatsApp Web with retries
    max_retries = settings.max_retries if settings else 2
    retry_delay = settings.retry_delay if settings else 3
    
    for attempt in range(max_retries + 1):
        try:
            return _open_whatsapp_web_internal(settings)
        except Exception as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)
                if settings and settings.debug_mode:
                    print(f"🔄 Browser launch retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise BrowserManagerError(f"Failed to open WhatsApp Web after {max_retries + 1} attempts: {e}")


def _open_whatsapp_web_internal(settings=None):
    """Internal method to open WhatsApp Web"""
    
    # --------------------------------------------------
    # 1️⃣ Check if WhatsApp Web tab already exists
    # --------------------------------------------------
    wa_win = find_whatsapp_tab()
    if wa_win:
        if settings and settings.debug_mode:
            print("✅ Reusing existing WhatsApp tab")
        bring_window_to_front(wa_win)
        return

    # --------------------------------------------------
    # Load browser config from settings
    # --------------------------------------------------
    if settings:
        browser = settings.browser
        profile = settings.browser_profile
        user_data_dir = settings.browser_user_data_dir
    else:
        # Fallback to old config
        try:
            from BACKEND.automations.whatsapp.whatsapp_config import load_config
            config = load_config()
            browser = config.get("browser", "edge")
            profile = config.get("profile", "Default")
            user_data_dir = ""
        except:
            browser = "edge"
            profile = "Default"
            user_data_dir = ""

    # Get browser path with fallback
    browser_path = get_browser_path(browser)
    
    if not browser_path:
        if settings and settings.debug_mode:
            print(f"⚠️ {browser} not found, trying fallback browsers...")
        
        # Try fallback browsers
        for fallback_browser in ["edge", "chrome", "brave"]:
            if fallback_browser != browser:
                fallback_path = get_browser_path(fallback_browser)
                if fallback_path:
                    browser = fallback_browser
                    browser_path = fallback_path
                    if settings and settings.debug_mode:
                        print(f"✅ Using fallback browser: {fallback_browser}")
                    break
        
        if not browser_path:
            raise BrowserManagerError("No supported browser found (Edge, Chrome, Brave)")

    # --------------------------------------------------
    # 2️⃣ Check if browser is already running
    # --------------------------------------------------
    if is_browser_running(browser):
        if settings and settings.debug_mode:
            print(f"🔄 {browser.title()} is running, adding WhatsApp tab...")

        # Find and bring browser to front
        browser_win = find_browser_window()
        if browser_win:
            bring_window_to_front(browser_win)
            time.sleep(0.5)

        # Open WhatsApp in new tab
        try:
            launch_args = [browser_path, "--new-tab", WHATSAPP_URL]
            
            if profile and profile != "":
                launch_args.insert(1, f"--profile-directory={profile}")
            
            if user_data_dir and user_data_dir != "":
                launch_args.insert(1, f"--user-data-dir={user_data_dir}")
            
            subprocess.Popen(
                launch_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False
            )
            if settings and settings.debug_mode:
                print("✅ WhatsApp tab opened")
            return
        except Exception as e:
            if settings and settings.verbose_logging:
                print(f"⚠️ Failed to open new tab: {e}")
            # Fallback to URL handler
            subprocess.Popen(
                ["cmd", "/c", "start", WHATSAPP_URL],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            return

    # --------------------------------------------------
    # 3️⃣ Launch fresh browser instance
    # --------------------------------------------------
    if settings and settings.debug_mode:
        print(f"🚀 Launching fresh {browser.title()} instance...")
    
    try:
        launch_args = [browser_path, f"--app={WHATSAPP_URL}", "--new-window"]
        
        if profile and profile != "":
            launch_args.insert(1, f"--profile-directory={profile}")
        
        if user_data_dir and user_data_dir != "":
            launch_args.insert(1, f"--user-data-dir={user_data_dir}")
        
        subprocess.Popen(
            launch_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False
        )
        if settings and settings.debug_mode:
            print(f"✅ New {browser.title()} window opened with WhatsApp")
    except Exception as e:
        if settings and settings.verbose_logging:
            print(f"⚠️ Failed to launch browser: {e}")
        # Fallback to URL handler
        subprocess.Popen(
            ["cmd", "/c", "start", WHATSAPP_URL],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True
        )
