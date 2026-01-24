import threading
import platform
import traceback
from playsound import playsound

# Your imported modules (make sure these are all correct and available)
from AUTOMATION.MAIN_INTEGRATION._integration_automation import *
from BRAIN.MAIN_BRAIN.BRAIN.brain import *
from FUNCTION.LOGGER.logger import append_response
from FUNCTION.MAIN_FUNCTION_INTEGRATION.function_integration import *
from BRAIN.ACTIVITY.GREETINGS.welcome_greetings import *
from BRAIN.ACTIVITY.GREETINGS.wish_greetings import *
from BRAIN.ACTIVITY.ADVICE.advice import *
from BRAIN.ACTIVITY.JOKE.jokes import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_plug_check import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_alert import *
from UTILS.path_utils import *
from UTILS.tts_singleton import speak

RESPONSES_FILE = TD("Responses.data")

def comain():
    current_mode = "main"

    while True:
        try:

            text = listen()
            if text is None:
                continue
            text = text.lower().strip()
            append_response(user_msg=text)

            if "turn to normal chat" in text:
                current_mode = "chat"
                speak("Switched to normal conversation mode.")
                continue
            elif "return to main mode" in text:
                current_mode = "main"
                speak("Returning to main Jarvis mode.")
                continue

            if current_mode == "main":
                Automation(text)
                Function_cmd(text)
                Greetings(text)
                if text in bye_key_word:
                    x = random.choice(res_bye)
                    speak(x)
                elif "jarvis" in text:
                    response = brain_cmd(text)
                    speak(response)
            elif current_mode == "chat":
                # Add chat mode processing here if needed
                pass

        except Exception as e:
            print(f"[comain Error] {e}")
            traceback.print_exc()


def main():
    welcome()  # Play greeting/welcome messages (make sure this doesn't block forever)
    comain()


def jarvis():
    try:
        # Play startup sound before launching threads
        sound_path = resource_path("DATA/soundeffect/mixkit-high-tech-bleep-2521.wav")
        playsound(sound_path)

        # Main listening thread (not daemon, so program waits here)
        t1 = threading.Thread(target=main)

        # Background worker threads marked as daemon so they exit when main exits
        t2 = threading.Thread(target=battery_alert, daemon=True)
        t3 = threading.Thread(target=check_plugin_status, daemon=True)
        t4 = threading.Thread(target=advice, daemon=True)
        t5 = threading.Thread(target=jokes, daemon=True)

        # Start all threads
        t1.start()
        t2.start()
        t3.start()
        t4.start()
        t5.start()

        # Only wait for the main thread to finish (which it probably never will while listening)
        t1.join()

        print("Main listening thread ended, exiting program...")

    except Exception as e:
        print(f"[Jarvis Error] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    jarvis()
