import random
import pyautogui as ui
from DATA.JARVIS_DLG_DATASET.DLG import closedlg
from FUNCTION.JARVIS_SPEAK.speak import speak

closedlg_random = random.choice(closedlg)
def close():
    speak(closedlg_random)
    ui.hotkey("alt","f4")