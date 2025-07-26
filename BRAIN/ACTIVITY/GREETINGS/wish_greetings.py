import random
from datetime import date
import datetime

from DATA.JARVIS_DLG_DATASET.DLG import *
<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import speak
=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)

today = date.today()
formatted_date = today.strftime("%d %b, %y")
nowx = datetime.datetime.now()

def wish():
    current_hour = nowx.hour
    if 5<= current_hour <= 12:
        gd_dlg = random.choice(good_morningdlg)
        speak(gd_dlg)
    else:
        gn_dlg = random.choice(good_nightdlg)
        speak(gn_dlg)

def Greetings(text):
    if "good morning" in text or "good afternoon" in text or "good evening" in text or "good night" in text:
        wish()
    else:
        pass