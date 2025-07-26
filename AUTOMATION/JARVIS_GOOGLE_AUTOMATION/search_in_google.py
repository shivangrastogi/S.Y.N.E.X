import pywhatkit
import random
from DATA.JARVIS_DLG_DATASET.DLG import search_result
<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import speak
=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)


def search_google(text):
    if "search" in text.lower():
        text = text.lower().replace("search", "").strip()
    dlg = random.choice(search_result)
    pywhatkit.search(text)
    speak(dlg)

