# BACKEND/automations/browser/window_utils.py
import ctypes
import time

def bring_window_to_front(win):
    hwnd = win._hWnd
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)