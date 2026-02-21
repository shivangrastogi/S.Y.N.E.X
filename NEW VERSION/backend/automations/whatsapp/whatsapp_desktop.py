# BACKEND/automations/whatsapp/whatsapp_desktop.py
"""
Enhanced WhatsApp Desktop automation with retry logic and error handling
"""

import subprocess
import time
import pyautogui
import os
import psutil
from typing import Optional

try:
    from BACKEND.automations.whatsapp.whatsapp_automation_config import get_settings
except ImportError:
    get_settings = None

from BACKEND.automations.whatsapp.whatsapp_state import (
    WHATSAPP_READY,
    WHATSAPP_DESKTOP_TIMEOUT
)



def is_whatsapp_running():
    """Check if WhatsApp process is already running"""
    for proc in psutil.process_iter(['name']):
        try:
            if 'whatsapp' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


class WhatsAppDesktopError(Exception):
    """Custom exception for WhatsApp Desktop errors"""
    pass


class WhatsAppDesktop:
    """Enhanced WhatsApp Desktop controller with retry logic and error handling"""

    def __init__(self):
        self.settings = get_settings() if get_settings else None
        self._is_ready = False

    def open(self):
        """Open WhatsApp Desktop with retry logic"""
        
        settings = self.settings
        max_retries = settings.max_retries if settings else 2
        retry_delay = settings.retry_delay if settings else 3
        
        for attempt in range(max_retries + 1):
            try:
                return self._open_internal()
            except Exception as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (attempt + 1)
                    if settings and settings.debug_mode:
                        print(f"🔄 Retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise WhatsAppDesktopError(f"Failed to open WhatsApp Desktop after {max_retries + 1} attempts: {e}")

    def _open_internal(self):
        """Internal method to open WhatsApp Desktop"""
        
        # If already running, bring to front
        if is_whatsapp_running():
            if self.settings and self.settings.debug_mode:
                print("🔄 WhatsApp is already running, bringing to front")
            self._bring_to_front()
            return

        if self.settings and self.settings.debug_mode:
            print("🚀 Launching WhatsApp Desktop...")

        # Get launch timeout from settings
        launch_timeout = self.settings.desktop_launch_timeout if self.settings else 10
        
        # Get launch methods from settings
        if self.settings and hasattr(self.settings, '_settings'):
            methods = self.settings._settings.get("desktop_launch_methods", ["direct", "uri", "explorer"])
        else:
            methods = ["direct", "uri", "explorer"]

        # Try multiple launch methods
        launch_attempts = {
            "direct": lambda: subprocess.Popen(
                [os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            ),
            "uri": lambda: subprocess.Popen(
                ["cmd", "/c", "start", "whatsapp:"],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            ),
            "explorer": lambda: subprocess.Popen(
                ["explorer.exe", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!WhatsAppDesktop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        }

        for method_name in methods:
            if method_name not in launch_attempts:
                continue
                
            try:
                method = launch_attempts[method_name]
                method()
                
                # Wait and check if launched
                start_wait = time.time()
                while time.time() - start_wait < launch_timeout:
                    if is_whatsapp_running():
                        if self.settings and self.settings.debug_mode:
                            print(f"✅ WhatsApp launched via {method_name}")
                        time.sleep(2)  # Extra stabilization time
                        return
                    time.sleep(0.5)
                    
            except Exception as e:
                if self.settings and self.settings.verbose_logging:
                    print(f"⚠️ Method {method_name} failed: {e}")
                continue

        raise WhatsAppDesktopError("Failed to launch WhatsApp Desktop with any method")

    def _bring_to_front(self):
        """Bring WhatsApp window to front"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle('WhatsApp')
            if windows:
                windows[0].activate()
                time.sleep(1)
        except Exception as e:
            if self.settings and self.settings.verbose_logging:
                print(f"⚠️ Failed to bring window to front: {e}")

    def send_message(self, contact: str, message: str):
        """Send message with retry logic and error handling"""
        
        global WHATSAPP_READY
        WHATSAPP_READY = False
        
        # Validate inputs
        if not contact or not message:
            raise ValueError("Contact and message must not be empty")
        
        settings = self.settings
        max_retries = settings.max_retries if settings else 2
        retry_delay = settings.retry_delay if settings else 3
        
        for attempt in range(max_retries + 1):
            try:
                return self._send_message_internal(contact, message)
            except Exception as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    if settings and settings.debug_mode:
                        print(f"🔄 Message send retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise WhatsAppDesktopError(f"Failed to send message after {max_retries + 1} attempts: {e}")

    def _send_message_internal(self, contact: str, message: str):
        """Internal method to send message"""
        
        # Open WhatsApp
        self.open()
        
        # Get load delay from settings
        load_delay = 3
        if self.settings and hasattr(self.settings, '_settings'):
            load_delay = self.settings._settings.get("chat_open_delay", 3)
        time.sleep(load_delay)

        # Wait until ready
        if not self._wait_until_ready():
            raise WhatsAppDesktopError("WhatsApp Desktop not ready")

        global WHATSAPP_READY
        WHATSAPP_READY = True
        self._is_ready = True
        
        # Send the message
        self._send(contact, message)

    def _wait_until_ready(self) -> bool:
        """Wait until WhatsApp is ready to receive input"""
        
        # Get timeout from settings
        timeout = self.settings.desktop_ready_timeout if self.settings else WHATSAPP_DESKTOP_TIMEOUT
        start = time.time()

        if self.settings and self.settings.debug_mode:
            print("⏳ Waiting for WhatsApp Desktop to be ready...")

        while time.time() - start < timeout:
            try:
                # Safe readiness check
                pyautogui.click(100, 100)  # Click in safe corner
                time.sleep(0.5)

                # Try to open search
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.3)

                # Clear any existing text
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.press("backspace")

                if self.settings and self.settings.debug_mode:
                    print("✅ WhatsApp Desktop is ready")
                return True

            except Exception as e:
                elapsed = int(time.time() - start)
                if self.settings and self.settings.verbose_logging:
                    print(f"⏳ Still waiting... ({elapsed}s / {timeout}s)")
                time.sleep(1)

        if self.settings and self.settings.debug_mode:
            print(f"❌ WhatsApp Desktop timeout after {timeout}s")
        return False

    def _send(self, contact: str, message: str):
        """Send message through WhatsApp Desktop with settings integration"""
        
        if self.settings and self.settings.debug_mode:
            print(f"📤 Sending to {contact}: {message[:50]}...")

        # Get typing interval from settings
        typing_interval = self.settings.typing_interval if self.settings else 0.05
        
        # Open search
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)

        # Clear search field
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.3)

        # Type contact
        pyautogui.typewrite(contact, interval=typing_interval)
        time.sleep(1)

        # Select contact
        pyautogui.press("enter")
        time.sleep(1)

        # Type and send message
        # Use pyperclip for Unicode/Hinglish support
        try:
            import pyperclip
            pyperclip.copy(message)
            pyautogui.hotkey("ctrl", "v")
        except ImportError:
            # Fallback to typewrite
            pyautogui.typewrite(message, interval=typing_interval)
        
        # Get send delay from settings
        send_delay = self.settings.send_delay if self.settings else 0.5
        time.sleep(send_delay)
        
        pyautogui.press("enter")

        if self.settings and self.settings.debug_mode:
            print("✅ Message sent successfully")
