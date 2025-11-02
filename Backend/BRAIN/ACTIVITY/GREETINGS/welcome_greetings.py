import random

from DATA.JARVIS_DLG_DATASET.DLG import welcomedlg
from FUNCTION.JARVIS_SPEAK.speak import speak


def welcome():
    welcome = random.choice(welcomedlg)
    speak(welcome)
