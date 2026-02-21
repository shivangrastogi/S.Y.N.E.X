import types
import unittest
from unittest.mock import patch, MagicMock

from BACKEND.automations.google.google_native import (
    search_google_native,
    native_back,
    native_forward,
    native_refresh,
    native_scroll_down,
    native_scroll_up,
    native_scroll_top,
    native_scroll_bottom,
    native_new_tab,
    native_close_tab,
    native_next_tab,
    native_previous_tab,
)


class FakeWin:
    def __init__(self, title="Google - Chrome"):
        self.title = title
        self.isMinimized = False
    def restore(self):
        self.isMinimized = False
    def activate(self):
        pass


class GoogleNativeTest(unittest.TestCase):
    def setUp(self):
        # Patch window discovery to return our fake window
        self.win_patch = patch(
            "BACKEND.automations.google.google_native.find_active_browser_window",
            return_value=FakeWin(),
        )
        self.win_patch.start()
        # No-op bring to front
        self.front_patch = patch(
            "BACKEND.automations.browser.window_utils.bring_window_to_front",
            lambda w: None,
        )
        self.front_patch.start()
        # Track pyautogui calls
        self.calls = {"hotkey": [], "press": [], "typewrite": []}
        self.hotkey_patch = patch("pyautogui.hotkey", side_effect=lambda *a: self.calls["hotkey"].append(a))
        self.press_patch = patch("pyautogui.press", side_effect=lambda k: self.calls["press"].append(k))
        self.write_patch = patch("pyautogui.typewrite", side_effect=lambda s, interval=0.0: self.calls["typewrite"].append(s))
        self.scroll_patch = patch("pyautogui.scroll", side_effect=lambda v: self.calls.setdefault("scroll", []).append(v))
        for p in [self.hotkey_patch, self.press_patch, self.write_patch, self.scroll_patch]:
            p.start()

    def tearDown(self):
        for p in [self.win_patch, self.front_patch, self.hotkey_patch, self.press_patch, self.write_patch, self.scroll_patch]:
            try:
                p.stop()
            except Exception:
                pass

    def test_search_google_native_sends_url(self):
        ok = search_google_native("hello world")
        self.assertTrue(ok)
        self.assertIn("https://www.google.com/search?q=hello+world", " ".join(self.calls["typewrite"]))
        self.assertIn("enter", self.calls["press"])  # Enter key sent

    def test_nav_hotkeys(self):
        self.assertTrue(native_back())
        self.assertTrue(native_forward())
        self.assertTrue(native_refresh())
        hk = self.calls["hotkey"]
        self.assertIn(("alt", "left"), hk)
        self.assertIn(("alt", "right"), hk)
        self.assertIn("f5", self.calls["press"])  # refresh

    def test_scroll(self):
        self.assertTrue(native_scroll_down())
        self.assertTrue(native_scroll_up())
        self.assertTrue(native_scroll_top())
        self.assertTrue(native_scroll_bottom())
        self.assertTrue(len(self.calls.get("scroll", [])) >= 2)
        hk = self.calls["hotkey"]
        # top/bottom use ctrl+home/end
        found_top = any(t == ("ctrl", "home") for t in hk)
        found_bottom = any(t == ("ctrl", "end") for t in hk)
        self.assertTrue(found_top)
        self.assertTrue(found_bottom)

    def test_tabs(self):
        self.assertTrue(native_new_tab())
        self.assertTrue(native_close_tab())
        self.assertTrue(native_next_tab())
        self.assertTrue(native_previous_tab())
        hk = self.calls["hotkey"]
        self.assertIn(("ctrl", "t"), hk)
        self.assertIn(("ctrl", "w"), hk)
        self.assertIn(("ctrl", "tab"), hk)
        self.assertIn(("ctrl", "shift", "tab"), hk)


if __name__ == "__main__":
    unittest.main()
