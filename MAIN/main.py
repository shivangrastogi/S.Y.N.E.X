#main.py
# import random
from AUTOMATION.MAIN_INTEGRATION._integration_automation import *
# import winsound
from BRAIN.MAIN_BRAIN.BRAIN.brain import *

from FUNCTION.MAIN_FUNCTION_INTEGRATION.function_integration import *
from BRAIN.ACTIVITY.GREETINGS.welcome_greetings import *
from BRAIN.ACTIVITY.GREETINGS.wish_greetings import *
import threading
from BRAIN.ACTIVITY.ADVICE.advice import *
from BRAIN.ACTIVITY.JOKE.jokes import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_plug_check import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_alert import *
from FUNCTION.JARVIS_SPEAK.speak import speak
from UTILS.path_utils import TD
import subprocess
import os

RESPONSES_FILE = TD("Responses.data")

def comain():
    while True:
        text = listen().lower()
        text = text.replace("jar", "jarvis")
        append_response(user_msg=text)
        Automation(text)
        Function_cmd(text)
        Greetings(text)

        if text in bye_key_word:
            x = random.choice(res_bye)
            speak(x)

        elif "jarvis" in text or "jar" in text:
            response = brain_cmd(text)
            speak(response)

        else:
            pass

def main():
    welcome()
    comain()

# def main():
#     while True:
#         # wake_cmd = hearing().lower()
#         # if wake_cmd in wake_key_word:
#         welcome()
#         comain()
#         # else:
#         #     pass

def jarvis():
    try:
        sound_path = resource_path("DATA/soundeffect/mixkit-high-tech-bleep-2521.wav")
        playsound(sound_path)
        t1 = threading.Thread(target=main)
        t2 = threading.Thread(target=battery_alert)
        t3 = threading.Thread(target=check_plugin_status)
        t4 = threading.Thread(target=advice)
        t5 = threading.Thread(target=jokes)
        for t in [t1, t2, t3, t4, t5]:
            t.start()
        for t in [t1, t2, t3, t4, t5]:
            t.join()
    except Exception as e:
        print(f"[Jarvis Error] {e}")


if __name__ == "__main__":
    jarvis()
