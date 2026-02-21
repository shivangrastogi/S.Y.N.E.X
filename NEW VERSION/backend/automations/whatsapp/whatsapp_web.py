# BACKEND/automations/whatsapp/whatsapp_web.py
"""
Enhanced WhatsApp Web automation with retry logic and error handling
"""

import time
import pyautogui
import pygetwindow as gw
import ctypes

from BACKEND.automations.whatsapp.browser_manager import open_whatsapp_web
from BACKEND.automations.whatsapp.whatsapp_state import (
    WHATSAPP_READY,
    WHATSAPP_WEB_DELAY
)

try:
    from BACKEND.automations.whatsapp.whatsapp_automation_config import get_settings
except ImportError:
    get_settings = None


class WhatsAppWebError(Exception):
    """Custom exception for WhatsApp Web errors"""
    pass


class WhatsAppWeb:
    """Enhanced WhatsApp Web controller with retry logic and error handling"""

    def __init__(self):
        self.settings = get_settings() if get_settings else None
        self._is_ready = False

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
                        print(f"🔄 WhatsApp Web retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise WhatsAppWebError(f"Failed to send message after {max_retries + 1} attempts: {e}")

    def _send_message_internal(self, contact: str, message: str):
        """Internal method to send message"""
        
        # Open WhatsApp Web
        open_whatsapp_web()
        
        # Get load delay from settings
        load_delay = self.settings.web_load_delay if self.settings else WHATSAPP_WEB_DELAY
        if self.settings and self.settings.debug_mode:
            print(f"⏳ Waiting {load_delay}s for WhatsApp Web to load...")
        time.sleep(load_delay)

        # Ensure keyboard focus
        self._prime_ui()

        # Wait until ready
        if not self._wait_until_ready():
            raise WhatsAppWebError("WhatsApp Web not ready")

        global WHATSAPP_READY
        WHATSAPP_READY = True
        self._is_ready = True
        
        # Send the message
        self._send(contact, message)

    # ----------------------------------
    # CORE SEND LOGIC (ENHANCED)
    # ----------------------------------
    def _send(self, contact: str, message: str):
        """Send message through WhatsApp Web with settings integration"""
        
        if not WHATSAPP_READY:
            raise WhatsAppWebError("WhatsApp Web is not ready")

        if self.settings and self.settings.debug_mode:
            print(f"📤 Sending to {contact}: {message[:50]}...")

        # Get typing interval from settings
        typing_interval = self.settings.typing_interval if self.settings else 0.05
        search_clear_delay = self.settings._settings.get("search_clear_delay", 0.3) if self.settings else 0.3
        chat_open_delay = self.settings._settings.get("chat_open_delay", 1.2) if self.settings else 1.2

        # Open search
        pyautogui.hotkey("ctrl", "alt", "/")
        time.sleep(0.6)

        # Clear search box
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(search_clear_delay)

        # Type contact name
        pyautogui.typewrite(contact, interval=typing_interval)
        time.sleep(1)

        # Open chat
        pyautogui.press("enter")
        time.sleep(chat_open_delay)

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
            print("✅ Message sent successfully via WhatsApp Web")

    # ----------------------------------
    # WINDOW CONTROL
    # ----------------------------------
    def _bring_whatsapp_to_front(self):
        """Bring WhatsApp Web window to front"""
        try:
            windows = (
                gw.getWindowsWithTitle("WhatsApp")
                or gw.getWindowsWithTitle("Microsoft Edge")
                or gw.getWindowsWithTitle("Google Chrome")
                or gw.getWindowsWithTitle("Brave")
            )

            if not windows:
                if self.settings and self.settings.verbose_logging:
                    print("⚠️ No WhatsApp window found")
                return

            win = windows[0]
            hwnd = win._hWnd

            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 5)
            user32.SetForegroundWindow(hwnd)
            time.sleep(1)
            
            if self.settings and self.settings.debug_mode:
                print("✅ WhatsApp window brought to front")
        except Exception as e:
            if self.settings and self.settings.verbose_logging:
                print(f"⚠️ Failed to bring window to front: {e}")

    # ----------------------------------
    # UI PRIME (SAFE CLICK)
    # ----------------------------------
    def _prime_ui(self):
        """Prime UI with safe click"""
        try:
            ui_prime_delay = self.settings._settings.get("ui_prime_delay", 0.3) if self.settings else 0.3
            w, h = pyautogui.size()
            pyautogui.click(w // 2, h // 2)
            time.sleep(ui_prime_delay)
        except Exception as e:
            if self.settings and self.settings.verbose_logging:
                print(f"⚠️ UI prime failed: {e}")

    def _wait_until_ready(self, timeout: int = None) -> bool:
        """Wait until WhatsApp Web is ready to receive input"""
        
        if timeout is None:
            timeout = self.settings.web_ready_timeout if self.settings else 30
        
        start = time.time()
        
        if self.settings and self.settings.debug_mode:
            print("⏳ Waiting for WhatsApp Web to be ready...")
        
        while time.time() - start < timeout:
            try:
                pyautogui.hotkey("ctrl", "alt", "/")
                time.sleep(0.4)
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.press("backspace")
                
                if self.settings and self.settings.debug_mode:
                    print("✅ WhatsApp Web is ready")
                return True
            except Exception as e:
                elapsed = int(time.time() - start)
                if self.settings and self.settings.verbose_logging:
                    print(f"⏳ Still waiting... ({elapsed}s / {timeout}s)")
                time.sleep(1)
        
        if self.settings and self.settings.debug_mode:
            print(f"❌ WhatsApp Web timeout after {timeout}s")
        return False

