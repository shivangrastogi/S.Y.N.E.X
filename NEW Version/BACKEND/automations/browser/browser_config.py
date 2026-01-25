# BACKEND/automations/browser/browser_config.py
import json
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_PATH = os.path.join(BASE_DIR, "DATA", "config", "browser.json")


def get_browser_choice():
    if not os.path.exists(CONFIG_PATH):
        return None

    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f).get("browser")
    except Exception:
        return None


def save_browser_choice(browser: str):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"browser": browser}, f)
