import random
import pyautogui as ui
from DATA.JARVIS_DLG_DATASET.DLG import closedlg
from UTILS.tts_singleton import speak

def close():
    closedlg_random = random.choice(closedlg)
    speak(closedlg_random)
    ui.hotkey("alt","f4")