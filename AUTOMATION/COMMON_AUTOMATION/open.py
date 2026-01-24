import time
import pyautogui as ui
from DATA.JARVIS_DLG_DATASET.DLG import open_dld
import random
from UTILS.tts_singleton import speak


def open(text):
    if not text.strip():
        speak("I didn't catch the app name.")
        return
    x = random.choice(open_dld)
    speak(x + " " + text)
    time.sleep(0.5)
    ui.hotkey("win")
    time.sleep(0.2)
    ui.write(text)
    time.sleep(0.5)
    ui.press("enter")
