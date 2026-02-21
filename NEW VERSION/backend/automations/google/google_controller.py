# BACKEND/automations/google/google_controller.py

from BACKEND.automations.google.google_session import (
    GoogleSession,
    GoogleBlockedError
)
from BACKEND.automations.google.google_search import search_google
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
from BACKEND.automations.google.google_pages import open_website
from BACKEND.automations.google.google_scroll import (
    scroll_down, scroll_up, scroll_to_top, scroll_to_bottom
)
from BACKEND.automations.google.google_navigation import (
    open_new_tab, close_tab, next_tab, previous_tab,
    go_back, go_forward, refresh
)
from BACKEND.automations.google.google_config import get_settings


class GoogleController:
    def __init__(self):
        self.session = GoogleSession()
        self.settings = get_settings()

    def _driver(self):
        return self.session.get_driver()
    
    def _should_use_native(self) -> bool:
        """Check if native automation should be attempted based on settings."""
        cfg = self.settings.get_config()
        return cfg.prefer_native

    def search(self, query: str):
        cfg = self.settings.get_config()
        
        # Try native if enabled
        if self._should_use_native():
            did_native = False
            try:
                did_native = search_google_native(query)
                if cfg.debug:
                    print(f"[Google] Native search: {'succeeded' if did_native else 'no browser'}")
            except Exception as e:
                if cfg.debug:
                    print(f"[Google] Native search failed: {e}")
                did_native = False
            
            if did_native:
                return
            
            # Don't fallback if native-only mode
            if not cfg.allow_selenium_fallback:
                raise GoogleBlockedError("Native mode enabled but no active browser found.")
        
        # Fallback: Selenium-controlled session (may be blocked in some environments)
        if self.session.is_blocked():
            raise GoogleBlockedError("Google CAPTCHA detected.")
        if cfg.debug:
            print("[Google] Using Selenium search")
        search_google(self._driver(), query)

    def open_site(self, name: str):
        open_website(self._driver(), name)

    def scroll_down(self):
        if self._should_use_native() and native_scroll_down():
            return
        scroll_down(self._driver())

    def scroll_up(self):
        if self._should_use_native() and native_scroll_up():
            return
        scroll_up(self._driver())

    def scroll_top(self):
        if self._should_use_native() and native_scroll_top():
            return
        scroll_to_top(self._driver())

    def scroll_bottom(self):
        if self._should_use_native() and native_scroll_bottom():
            return
        scroll_to_bottom(self._driver())

    def new_tab(self):
        if self._should_use_native() and native_new_tab():
            return
        open_new_tab(self._driver())

    def close_tab(self):
        if self._should_use_native() and native_close_tab():
            return
        close_tab(self._driver())

    def next_tab(self):
        if self._should_use_native() and native_next_tab():
            return
        next_tab(self._driver())

    def previous_tab(self):
        if self._should_use_native() and native_previous_tab():
            return
        previous_tab(self._driver())

    def back(self):
        if self._should_use_native() and native_back():
            return
        go_back(self._driver())

    def forward(self):
        if self._should_use_native() and native_forward():
            return
        go_forward(self._driver())

    def refresh(self):
        if self._should_use_native() and native_refresh():
            return
        refresh(self._driver())

    def close(self):
        self.session.close()
