# BACKEND/automations/youtube/youtube_cmd.py
import time
import webbrowser
import pyautogui

from BACKEND.automations.youtube.youtube_native import open_youtube_native


def _open_youtube_native(query: str):
    """
    Opens YouTube search in an already opened Brave instance.
    Falls back safely if Brave is not running.
    """

    try:
        open_youtube_native(query)
    except Exception:
        search_url = (
            "https://www.youtube.com/results?search_query="
            + query.replace(" ", "+")
        )
        webbrowser.open(search_url)


def youtube_cmd(text: str):
    text = text.lower()

    # 🎵 PLAY COMMAND
    if "play" in text:
        query = (
            text.replace("play", "")
            .replace("on youtube", "")
            .replace("youtube", "")
            .strip()
        )

        if not query:
            return "What should I play on YouTube?"

        _open_youtube_native(query)
        return f"Playing {query} on YouTube."

    # 🔍 SEARCH COMMAND
    if "search" in text and "youtube" in text:
        query = (
            text.replace("search", "")
            .replace("on youtube", "")
            .replace("youtube", "")
            .strip()
        )

        if not query:
            return "What should I search on YouTube?"

        _open_youtube_native(query)
        return f"Searching {query} on YouTube."

    return None
