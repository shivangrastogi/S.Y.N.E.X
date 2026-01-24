import random

from DATA.JARVIS_DLG_DATASET.DLG import welcomedlg
from UTILS.tts_singleton import speak


def welcome():
    welcome = random.choice(welcomedlg)
    speak(welcome)
