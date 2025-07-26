import random
import pyautogui as ui
from DATA.JARVIS_DLG_DATASET.DLG import closedlg
<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import speak

=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)

def close():
    closedlg_random = random.choice(closedlg)
    speak(closedlg_random)
    ui.hotkey("alt","f4")