# BACKEND/automations/browser/brave_utils.py
import pygetwindow as gw
import time


def find_brave_window():
    for win in gw.getAllWindows():
        if win.title and "brave" in win.title.lower():
            return win
    return None


def focus_brave():
    """
    Brings an already opened Brave window to foreground.
    Returns True if focused, False otherwise.
    """
    win = find_brave_window()
    if win:
        try:
            if win.isMinimized:
                win.restore()

            win.activate()
            time.sleep(0.6)  # 🔑 REQUIRED for Windows focus
            return True
        except Exception:
            pass
    return False
