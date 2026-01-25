# BACKEND/automations/youtube/youtube_native.py
import time
import subprocess
import pyautogui
import webbrowser
from BACKEND.automations.browser.brave_utils import find_brave_window
from BACKEND.automations.browser.window_utils import bring_window_to_front

YOUTUBE_BASE = "https://www.youtube.com"

def open_youtube_native(query: str):
    """
    Uses existing Brave instance if available.
    Opens YouTube search in SAME browser.
    """

    brave = find_brave_window()

    if brave:
        bring_window_to_front(brave)
        time.sleep(0.5)

        # Open new tab in same window
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.3)

    else:
        # No Brave open → try opening Brave, else fallback to default browser
        try:
            subprocess.Popen(["brave", YOUTUBE_BASE])
            time.sleep(5)

            pyautogui.hotkey("ctrl", "t")
            time.sleep(0.3)
        except Exception:
            webbrowser.open(YOUTUBE_BASE)
            time.sleep(3)

    search_url = (
        "https://www.youtube.com/results?search_query="
        + query.replace(" ", "+")
    )

    try:
        pyautogui.typewrite(search_url)
        pyautogui.press("enter")
    except Exception:
        webbrowser.open(search_url)
        return

    time.sleep(3)

    # Focus first video (keyboard-based, human-like)
    pyautogui.press("tab", presses=6, interval=0.1)
    pyautogui.press("enter")
