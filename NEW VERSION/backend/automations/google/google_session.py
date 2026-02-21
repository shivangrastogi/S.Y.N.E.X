# BACKEND/automations/google/google_session.py
from BACKEND.automations.browser.browser_factory import create_browser
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

class GoogleBlockedError(Exception):
    """Custom exception for when Google blocks the automation."""
    pass

class GoogleSession:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.driver = None
        return cls._instance

    def _create_driver(self):
        self.driver = create_browser()
        try:
            self.driver.set_page_load_timeout(15)
        except Exception:
            pass
        self.driver.get("https://www.google.com")

    def get_driver(self):
        try:
            if not self.driver:
                self._create_driver()
            if not self.driver.window_handles:
                raise InvalidSessionIdException("No active window")
            _ = self.driver.current_url
            return self.driver
        except (InvalidSessionIdException, WebDriverException, Exception):
            self._safe_restart()
            return self.driver

    def _safe_restart(self):
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass
        self._create_driver()

    def is_blocked(self):
        try:
            url = self.driver.current_url.lower()
            return "sorry/" in url or "captcha" in url
        except:
            return False

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None