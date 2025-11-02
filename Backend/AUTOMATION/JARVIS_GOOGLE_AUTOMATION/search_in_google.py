import pywhatkit
import random
from DATA.JARVIS_DLG_DATASET.DLG import search_result
from FUNCTION.JARVIS_SPEAK.speak import speak


def search_google(text):
    if "search" in text.lower():
        text = text.lower().replace("search", "").strip()
    dlg = random.choice(search_result)
    pywhatkit.search(text)
    speak(dlg)

