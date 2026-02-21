# BACKEND/automations/whatsapp/whatsapp_controller.py
"""
Enhanced WhatsApp controller with intelligent backend selection and comprehensive error handling
"""

import os
import subprocess
import winreg
import sys
import time
from typing import Literal, Optional, Tuple

from BACKEND.automations.whatsapp.whatsapp_web import WhatsAppWeb, WhatsAppWebError
from BACKEND.automations.whatsapp.whatsapp_desktop import WhatsAppDesktop, WhatsAppDesktopError
from BACKEND.automations.whatsapp.message_parser import parse_and_validate, MessageParserError

try:
    from BACKEND.automations.whatsapp.whatsapp_automation_config import get_settings
except ImportError:
    get_settings = None


def is_whatsapp_desktop_installed():
    """
    Check if WhatsApp Desktop is installed on the system
    Returns True if installed, False otherwise
    """
    # Check Windows Registry for installed apps
    try:
        uninstall_keys = [
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for uninstall_key in uninstall_keys:
                try:
                    with winreg.OpenKey(root, uninstall_key) as key:
                        for i in range(0, winreg.QueryInfoKey(key)[0]):
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if "WhatsApp" in display_name and "Desktop" in display_name:
                                        return True
                                except (FileNotFoundError, OSError):
                                    continue
                except FileNotFoundError:
                    continue

        # Check for Microsoft Store version
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-AppxPackage | Where-Object {$_.Name -like '*WhatsAppDesktop*'}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout and "WhatsAppDesktop" in result.stdout:
                return True
        except Exception:
            pass

    except Exception:
        pass

    # Check common installation paths
    common_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%ProgramFiles%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\WhatsApp\WhatsApp.exe"),
    ]

    return any(os.path.exists(path) for path in common_paths)


def can_launch_whatsapp_desktop():
    """
    Try to launch WhatsApp Desktop safely
    Returns True if successful, False otherwise
    """
    try:
        # Try multiple launch methods
        methods = [
            # Method 1: Direct executable
            lambda: subprocess.Popen(
                [os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            ),
            # Method 2: Store app
            lambda: subprocess.Popen(
                ["explorer.exe", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!WhatsAppDesktop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            ),
            # Method 3: Via start menu
            lambda: subprocess.Popen(
                ["start", "whatsapp:"],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        ]

        # Try each method until one works
        for method in methods:
            try:
                method()
                time.sleep(2)  # Give it time to launch
                if is_whatsapp_running():
                    return True
            except Exception:
                continue

        return False
    except Exception:
        return False


class WhatsAppControllerError(Exception):
    """Custom exception for WhatsApp controller errors"""
    pass


class WhatsAppController:
    """
    Enhanced WhatsApp controller with intelligent backend detection and fallback
    Supports Desktop, Web, and automatic selection with retry logic
    """

    def __init__(self):
        self.settings = get_settings() if get_settings else None
        self.backend = None
        self.use_desktop = False
        self._detect_and_set_backend()

    def _detect_and_set_backend(self):
        """
        Intelligently detect and set the appropriate WhatsApp backend
        Priority based on settings or auto-detection
        """
        
        if self.settings and self.settings.debug_mode:
            print("🔍 Detecting WhatsApp backend...")

        # Check preferred backend from settings
        preferred_backend = self.settings.preferred_backend if self.settings else "auto"
        
        if preferred_backend == "desktop":
            # Force desktop
            if is_whatsapp_desktop_installed():
                if self.settings and self.settings.debug_mode:
                    print("📱 Using WhatsApp Desktop (forced by settings)")
                self.backend = WhatsAppDesktop()
                self.use_desktop = True
            else:
                if self.settings and self.settings.fallback_enabled:
                    if self.settings.debug_mode:
                        print("⚠️ Desktop not found, falling back to Web")
                    self.backend = WhatsAppWeb()
                    self.use_desktop = False
                else:
                    raise WhatsAppControllerError("WhatsApp Desktop not found and fallback disabled")
                    
        elif preferred_backend == "web":
            # Force web
            if self.settings and self.settings.debug_mode:
                print("🌐 Using WhatsApp Web (forced by settings)")
            self.backend = WhatsAppWeb()
            self.use_desktop = False
            
        else:
            # Auto-detect (default)
            auto_detect = self.settings.auto_detect_desktop if self.settings else True
            
            if auto_detect and is_whatsapp_desktop_installed():
                if self.settings and self.settings.debug_mode:
                    print("📱 WhatsApp Desktop detected")
                
                # Check if we can actually launch it
                if can_launch_whatsapp_desktop():
                    if self.settings and self.settings.debug_mode:
                        print("✅ WhatsApp Desktop is launchable")
                    self.backend = WhatsAppDesktop()
                    self.use_desktop = True
                    return
                else:
                    if self.settings and self.settings.debug_mode:
                        print("⚠️ WhatsApp Desktop detected but cannot launch, falling back to web")

            # Fallback to WhatsApp Web
            if self.settings and self.settings.debug_mode:
                print("🌐 Using WhatsApp Web")
            self.backend = WhatsAppWeb()
            self.use_desktop = False

    def send_message(self, contact: str, message: str):
        """
        Send message with automatic retry and intelligent fallback
        
        Args:
            contact: Contact name or phone number
            message: Message content
            
        Raises:
            WhatsAppControllerError: If message sending fails
        """
        
        if not contact or not message:
            raise ValueError("Contact and message must be provided")

        fallback_enabled = self.settings.fallback_enabled if self.settings else True
        
        try:
            # First attempt with selected backend
            if self.settings and self.settings.debug_mode:
                backend_name = "Desktop" if self.use_desktop else "Web"
                print(f"📤 Sending via WhatsApp {backend_name}...")
            
            self.backend.send_message(contact, message)
            
            if self.settings and self.settings.debug_mode:
                print("✅ Message sent successfully")

        except (WhatsAppDesktopError, WhatsAppWebError) as e:
            if self.settings and self.settings.debug_mode:
                print(f"❌ Primary method failed: {e}")

            # If desktop failed and fallback enabled, try web
            if self.use_desktop and fallback_enabled:
                if self.settings and self.settings.debug_mode:
                    print("🔄 Desktop failed, trying WhatsApp Web fallback...")
                try:
                    web_backend = WhatsAppWeb()
                    web_backend.send_message(contact, message)
                    
                    if self.settings and self.settings.debug_mode:
                        print("✅ Message sent successfully via Web fallback")
                    
                    # Update backend for future messages
                    self.backend = web_backend
                    self.use_desktop = False
                    
                except WhatsAppWebError as web_error:
                    raise WhatsAppControllerError(
                        f"Both Desktop and Web failed. Desktop: {e}, Web: {web_error}"
                    )
            else:
                raise WhatsAppControllerError(f"Message send failed: {e}")
                
        except Exception as e:
            raise WhatsAppControllerError(f"Unexpected error sending message: {e}")

    def handle(self, text: str) -> str:
        """
        Main entry point for intent routing
        Parses message and sends via WhatsApp
        
        Args:
            text: User input text (e.g., "send message to John, hello")
            
        Returns:
            Response message
        """
        
        try:
            # Parse and validate message
            contact, message = parse_and_validate(text, self.settings)
            
            # Send message
            self.send_message(contact, message)
            
            return f"✅ Message sent to {contact}: {message[:30]}..."
            
        except MessageParserError as e:
            return f"❌ Failed to parse message: {e}"
        except WhatsAppControllerError as e:
            return f"❌ Failed to send message: {e}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"

    def get_settings(self) -> dict:
        """Get current WhatsApp automation settings"""
        if self.settings:
            return self.settings.get_all_settings()
        return {"error": "Settings not available"}

    def get_backend_info(self) -> dict:
        """Get information about current backend"""
        return {
            "backend": "desktop" if self.use_desktop else "web",
            "backend_class": self.backend.__class__.__name__,
            "fallback_enabled": self.settings.fallback_enabled if self.settings else True
        }
