# BACKEND/automations/youtube/yt_search.py
"""
Enhanced YouTube search with retry logic and error handling
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

try:
    from BACKEND.automations.youtube.youtube_automation_config import get_settings
except ImportError:
    get_settings = None

from BACKEND.automations.youtube.yt_exceptions import YouTubeSearchError


def search_only(driver, query: str):
    """
    Performs YouTube search and stays on results page.
    """
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "search_query"))
        )
    except Exception:
        driver.get(
            f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        )
        return

    search_box.clear()
    search_box.send_keys(query)
    search_box.send_keys(Keys.ENTER)

    # Wait for results page
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "ytd-video-renderer")
            )
        )
    except Exception:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#contents")
            )
        )


def search_and_play_first(driver, query: str):
    # ALWAYS force YouTube search URL
    driver.get(
        f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    )

    first_video = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "ytd-video-renderer a#video-title")
        )
    )

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        first_video
    )

    driver.execute_script(
        "arguments[0].click();",
        first_video
    )

    time.sleep(2)
