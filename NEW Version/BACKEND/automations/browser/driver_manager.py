# BACKEND/automations/browser/driver_manager.py
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

class DriverManager:
    @staticmethod
    def get_driver_path(browser: str):
        try:
            if browser == "chrome":
                return ChromeDriverManager().install()
            if browser == "edge":
                return EdgeChromiumDriverManager().install()
            raise ValueError(f"Unsupported browser: {browser}")
        except Exception as e:
            raise RuntimeError(f"Failed to sync driver for {browser}: {e}")