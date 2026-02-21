# BACKEND/automations/whatsapp/window_utils.py
import pygetwindow as gw
import ctypes
import time


def bring_window_to_front(win):
    hwnd = win._hWnd
    user32 = ctypes.windll.user32

    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.8)


def find_whatsapp_tab():
    """
    Returns WhatsApp Web window if already open
    """
    windows = gw.getWindowsWithTitle("WhatsApp")

    if windows:
        return windows[0]

    return None


def find_browser_window():
    """
    Finds any Edge or Chrome window
    """
    for title in ["Microsoft Edge", "Google Chrome"]:
        wins = gw.getWindowsWithTitle(title)
        if wins:
            return wins[0]
    return None
