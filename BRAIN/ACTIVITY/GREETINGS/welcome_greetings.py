import random

from DATA.JARVIS_DLG_DATASET.DLG import welcomedlg
<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import speak
=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)


def welcome():
    welcome = random.choice(welcomedlg)
    speak(welcome)
