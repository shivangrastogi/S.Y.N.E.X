# import random
from AUTOMATION.MAIN_INTEGRATION._integration_automation import *
# import winsound
from BRAIN.MAIN_BRAIN.BRAIN.brain import *
from FUNCTION.MAIN_FUNCTION_INTEGRATION.function_integration import *
from FUNCTION.JARVIS_LISTEN.listen import *
from DATA.JARVIS_DLG_DATASET.DLG import *
from BRAIN.ACTIVITY.GREETINGS.welcome_greetings import *
from BRAIN.ACTIVITY.GREETINGS.wish_greetings import *
import threading
from BRAIN.ACTIVITY.ADVICE.advice import *
from BRAIN.ACTIVITY.JOKE.jokes import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_plug_check import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_alert import *
from playsound import playsound
from FUNCTION.JARVIS_SPEAK.speak import speak

def comain():
    while True:
        text = listen().lower()
        text = text.replace("jar", "jarvis")
        Automation(text)
        Function_cmd(text)
        Greetings(text)

        if text in bye_key_word:
            x = random.choice(res_bye)
            speak(x)
            break
        elif "jarvis" in text or "jar" in text:
            response = brain_cmd(text)
            speak(response)
        else:
            pass

def main():
    while True:

        wake_cmd = hearing().lower()
        if wake_cmd in wake_key_word:
            welcome()
            comain()
        else:
            pass



def jarvis():

    # base_dir = os.path.dirname(os.path.abspath(__file__))
    # sound_path = os.path.join(base_dir, '..', 'DATA', 'soundeffect', 'mixkit-high-tech-bleep-2521.wav')
    # sound_path = os.path.abspath(sound_path)
    # sound_path = resource_path("mixkit-high-tech-bleep-2521.wav")

    speak("JARVIS ACTIVATED")
    # playsound(sound_path)
    t1 = threading.Thread(target=main)
    t2 = threading.Thread(target=battery_alert)
    t3 = threading.Thread(target=check_plugin_status)
    t4 = threading.Thread(target=advice)
    t5 = threading.Thread(target=jokes)
    t1.start()
    t2.start()
    t3.start()
    t4.start()
    t5.start()
    t1.join()
    t2.join()
    t3.join()
    t4.join()
    t5.join()
#
if(__name__ == "__main__"):
    jarvis()