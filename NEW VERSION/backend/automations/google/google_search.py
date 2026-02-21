# BACKEND/automations/google/google_search.py
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def type_like_human(element, text):
    """Types text letter-by-letter with random delays to mimic a human."""
    for char in text:
        element.send_keys(char)
        # Random delay between 0.05 and 0.2 seconds
        time.sleep(random.uniform(0.05, 0.2))


def search_google(driver, query: str):
    if "google.com" not in driver.current_url:
        driver.get("https://www.google.com")

    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.NAME, "q"))
        )
    except Exception:
        # Fallback to direct search URL if page elements fail
        driver.get(
            "https://www.google.com/search?q="
            + query.replace(" ", "+")
        )
        return

    # Clear previous text human-style
    search_box.click()
    search_box.send_keys(Keys.CONTROL + "a")
    search_box.send_keys(Keys.BACKSPACE)
    time.sleep(0.3)

    # Type query naturally
    type_like_human(search_box, query)

    time.sleep(0.5)
    search_box.send_keys(Keys.ENTER)

    # Wait for results (fallback if #search is not present)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "search"))
        )
    except Exception:
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div#main"))
            )
        except Exception:
            # Last-resort fallback: direct search URL
            driver.get(
                "https://www.google.com/search?q="
                + query.replace(" ", "+")
            )