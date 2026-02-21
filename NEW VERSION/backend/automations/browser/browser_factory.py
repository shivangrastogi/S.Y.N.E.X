# BACKEND/automations/browser/browser_factory.py
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions

from BACKEND.automations.browser.browser_config import (
    get_browser_choice,
    save_browser_choice
)
from BACKEND.automations.browser.driver_manager import DriverManager

# -------------------------
# Browser executable paths
# -------------------------
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def _detect_browser():
    """
    Auto-detect browser priority:
    1. Brave
    2. Chrome
    3. Edge
    """
    if os.path.exists(BRAVE_PATH):
        return "brave", BRAVE_PATH

    if os.path.exists(CHROME_PATH):
        return "chrome", CHROME_PATH

    if os.path.exists(EDGE_PATH):
        return "edge", EDGE_PATH

    return None, None


def create_browser():
    """
    Creates Selenium browser instance.
    Auto-falls back to Brave if nothing configured.
    """

    browser = get_browser_choice()
    chrome_options = ChromeOptions()
    edge_options = EdgeOptions()

    # ---------------------------------
    # CASE 1: Browser already configured
    # ---------------------------------
    if browser:
        if browser == "chrome":
            if not os.path.exists(CHROME_PATH):
                raise RuntimeError("Chrome not found at default path.")
            chrome_options.binary_location = CHROME_PATH
        elif browser == "edge":
            if not os.path.exists(EDGE_PATH):
                raise RuntimeError("Edge not found at default path.")
            edge_options.binary_location = EDGE_PATH
        elif browser == "brave":
            if not os.path.exists(BRAVE_PATH):
                raise RuntimeError("Brave not found at default path.")
            chrome_options.binary_location = BRAVE_PATH
        else:
            raise RuntimeError(f"Unsupported browser: {browser}")

    # ---------------------------------
    # CASE 2: Browser NOT configured → auto detect
    # ---------------------------------
    else:
        detected, path = _detect_browser()
        if not detected:
            raise RuntimeError(
                "No supported browser found (Brave / Chrome / Edge)"
            )

        print(f"[Browser] Auto-detected {detected.capitalize()}")
        save_browser_choice(detected)
        if detected == "edge":
            edge_options.binary_location = path
        else:
            chrome_options.binary_location = path

    # ---------------------------------
    # Common Selenium options
    # ---------------------------------
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    edge_options.add_argument("--disable-notifications")
    edge_options.add_argument("--start-maximized")

    if browser == "edge":
        driver_path = DriverManager.get_driver_path("edge")
        service = EdgeService(driver_path)
        return webdriver.Edge(service=service, options=edge_options)

    driver_path = DriverManager.get_driver_path("chrome")
    service = ChromeService(driver_path)
    return webdriver.Chrome(service=service, options=chrome_options)
