from playsound import playsound
from AUTOMATION.MAIN_INTEGRATION._integration_automation import *
from BRAIN.MAIN_BRAIN.BRAIN.brain import *
from FUNCTION.MAIN_FUNCTION_INTEGRATION.function_integration import *
from BRAIN.ACTIVITY.GREETINGS.welcome_greetings import *
from BRAIN.ACTIVITY.GREETINGS.wish_greetings import *
from BRAIN.ACTIVITY.ADVICE.advice import *
from BRAIN.ACTIVITY.JOKE.jokes import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_plug_check import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_alert import *

RESPONSES_FILE = TD("Responses.data")

def comain():
    while True:
            append_response(user_msg=text)
                Automation(text)
                Function_cmd(text)
                Greetings(text)
                if text in bye_key_word:
                    x = random.choice(res_bye)
                    speak(x)
                    response = brain_cmd(text)
                    speak(response)
                pass

def main():
    comain()


def jarvis():
    try:
        sound_path = resource_path("DATA/soundeffect/mixkit-high-tech-bleep-2521.wav")
        playsound(sound_path)
        t1 = threading.Thread(target=main)
    except Exception as e:
        print(f"[Jarvis Error] {e}")


if __name__ == "__main__":
    jarvis()
