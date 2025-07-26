from time import sleep

import pyautogui as ui
import random
import time
from DATA.JARVIS_DLG_DATASET.DLG import s2, s1
<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import speak
=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)
import pygetwindow as gw

def is_browser_active():
    active = gw.getActiveWindow()
    return active and "Chrome" in active.title


def search_manual(text):
    text = text .replace("search","")
    if is_browser_active():
        ui.press("/")
        ui.write(text)
        s12 = random.choice(s1)
        speak( s12)
        time.sleep(0.5)
        ui.press("enter")
        s12 = random.choice(s2)
        speak(s12)
    else:
        print("Browser not active")
