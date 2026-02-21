# BACKEND/automations/whatsapp/whatsapp_utils.py
import time
import pyautogui


def wait_for_whatsapp_ready(timeout=30):
    """
    Waits until WhatsApp Desktop is usable.
    Avoids sending message during syncing.
    """
    start = time.time()

    while time.time() - start < timeout:
        # Try to open search bar
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)

        # If typing works, WhatsApp is ready
        pyautogui.typewrite(" ")
        pyautogui.press("backspace")

        return True

    raise TimeoutError("WhatsApp did not become ready")
