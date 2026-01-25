import time
import urllib.parse
import ctypes
import psutil
import pyautogui
import pygetwindow as gw

from BACKEND.automations.browser.window_utils import bring_window_to_front


BROWSER_KEYWORDS = ["chrome", "edge", "brave", "firefox", "opera"]
BROWSER_PROCESSES = [
    "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"
]


def _get_foreground_process_name() -> str | None:
    """Return the process name of the foreground window (Windows only)."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc = psutil.Process(pid.value)
        return proc.name().lower()
    except Exception:
        return None


def find_active_browser_window():
    """Return a top-level browser window if one is present (process-aware)."""
    # Prefer current foreground if it's a browser
    name = _get_foreground_process_name()
    if name and name in BROWSER_PROCESSES:
        # Try mapping by title scan to get a handle we can focus
        try:
            for win in gw.getAllWindows():
                if win.title and name.split(".")[0] in win.title.lower():
                    return win
        except Exception:
            pass

    # Fallback: any browser window by title
    try:
        windows = gw.getAllWindows()
    except Exception:
        return None
    for win in windows:
        title = (win.title or "").lower()
        if any(k in title for k in BROWSER_KEYWORDS):
            return win
    return None


def _ensure_browser_focused() -> bool:
    """Try to ensure a browser window is frontmost; return True on success."""
    win = find_active_browser_window()
    if not win:
        return False
    try:
        if getattr(win, "isMinimized", False):
            win.restore()
        win.activate()
        time.sleep(0.3)
        return True
    except Exception:
        try:
            bring_window_to_front(win)
            return True
        except Exception:
            return False


def search_google_native(query: str) -> bool:
    """
    Search using the currently open browser tab by typing in the address bar.
    Returns True if a browser was found and keystrokes were sent; False otherwise.
    """
    if not _ensure_browser_focused():
        return False

    try:
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.08)
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        pyautogui.typewrite(url, interval=0.02)
        pyautogui.press("enter")
        return True
    except Exception:
        return False


# Native navigation and scrolling using keystrokes
def native_back() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("alt", "left")
        return True
    except Exception:
        return False


def native_forward() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("alt", "right")
        return True
    except Exception:
        return False


def native_refresh() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.press("f5")
        return True
    except Exception:
        return False


def native_scroll_down(steps: int = 6) -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.scroll(-int(steps * 120))
        return True
    except Exception:
        return False


def native_scroll_up(steps: int = 6) -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.scroll(int(steps * 120))
        return True
    except Exception:
        return False


def native_scroll_top() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("ctrl", "home")
        return True
    except Exception:
        return False


def native_scroll_bottom() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("ctrl", "end")
        return True
    except Exception:
        return False


# Native tab management

def native_new_tab() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("ctrl", "t")
        return True
    except Exception:
        return False


def native_close_tab() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("ctrl", "w")
        return True
    except Exception:
        return False


def native_next_tab() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("ctrl", "tab")
        return True
    except Exception:
        return False


def native_previous_tab() -> bool:
    if not _ensure_browser_focused():
        return False
    try:
        pyautogui.hotkey("ctrl", "shift", "tab")
        return True
    except Exception:
        return False
