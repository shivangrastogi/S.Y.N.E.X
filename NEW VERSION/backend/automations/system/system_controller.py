# Path: d:\New folder (2) - JARVIS\backend\automations\system\system_controller.py
# backend/automations/system/system_controller.py
import os
import subprocess
import platform

try:
    import pyautogui
except ImportError:
    pyautogui = None

class SystemController:
    """
    Handles system-level automations like volume, brightness, and power states.
    """
    def __init__(self):
        self.os_name = platform.system()

    def handle(self, intent, text):
        text_lower = text.lower()
        
        if intent == "volume_mute" or "mute" in text_lower:
            return self.toggle_mute()
        elif intent == "volume_up" or "volume badhao" in text_lower or "increase volume" in text_lower:
            return self.change_volume(increase=True)
        elif intent == "volume_down" or "volume kam karo" in text_lower or "decrease volume" in text_lower:
            return self.change_volume(increase=False)
        elif "brightness" in text_lower:
            if any(w in text_lower for w in ["up", "increase", "badhao"]):
                return self.change_brightness(increase=True)
            else:
                return self.change_brightness(increase=False)
        
        return "I'm not sure how to control that system setting yet."

    def toggle_mute(self):
        if self.os_name == "Windows":
            if pyautogui:
                pyautogui.press("volumemute")
                return "System muted/unmuted."
            else:
                # Fallback to nircmd if available or power-shell
                subprocess.run(["powershell", "-Command", "(new-object -com wscript.shell).SendKeys([char]173)"], capture_output=True)
                return "Attempted to toggle mute via PowerShell."
        return "Mute control is only supported on Windows for now."

    def change_volume(self, increase=True):
        key = "volumeup" if increase else "volumedown"
        action = "Increased" if increase else "Decreased"
        if self.os_name == "Windows":
            if pyautogui:
                # Press multiple times for noticeable change
                for _ in range(5):
                    pyautogui.press(key)
                return f"{action} system volume."
            else:
                # PowerShell fallback (unreliable for increments)
                return f"Please install pyautogui for better volume control."
        return f"{action} volume is only supported on Windows."

    def change_brightness(self, increase=True):
        # Brightness is trickier without specific tools, but we can try WMI on Windows
        if self.os_name == "Windows":
            try:
                import screen_brightness_control as sbc
                current = sbc.get_brightness()[0]
                new = min(100, current + 10) if increase else max(0, current - 10)
                sbc.set_brightness(new)
                return f"Brightness set to {new}%"
            except ImportError:
                return "Brightness control requires 'screen-brightness-control' library. Please install it."
            except Exception as e:
                return f"Failed to change brightness: {str(e)}"
        return "Brightness control is only supported on Windows."
