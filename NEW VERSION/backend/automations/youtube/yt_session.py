# BACKEND/automations/youtube/yt_session.py
from BACKEND.automations.browser.browser_factory import create_browser
from selenium.common.exceptions import (
    WebDriverException,
    InvalidSessionIdException
)


class YouTubeSession:
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
        self.driver.get("https://www.youtube.com")

    def get_driver(self):
        """
        Always returns a VALID driver.
        Recreates driver if browser was closed or crashed.
        """
        try:
            if self.driver is None:
                raise WebDriverException("Driver not initialized")

            if not self.driver.window_handles:
                raise WebDriverException("No active window")
            # 🔥 This line is CRITICAL
            _ = self.driver.current_url

            return self.driver

        except (WebDriverException, InvalidSessionIdException):
            # Browser was closed / crashed / disconnected
            self._create_driver()
            return self.driver

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
