from FUNCTION.CHECK_TEMPERATURE.check_temperature import *
from FUNCTION.CHECK_INTERNET_SPEED.check_speed import *
from FUNCTION.CHECK_ONLINE_OFFLINE_STATUS.check_online_offline_status import *
from FUNCTION.CONTENT_GENERATION.content_writer import generate_content_file
from FUNCTION.AI_MEMORY.memory import remember, recall_memory, forget_all
from FUNCTION.GESTURE_RECOGNITION.voice_controller import VolumeGestureController
import FUNCTION.LLM_CHAT.llm_chat as normal_chat
from FUNCTION.MUSIC_WITH_CLAP.clap_with_music import *
from FUNCTION.CLOCK.clock import *
from FUNCTION.FIND_MY_IP.find_my_ip import *
from FUNCTION.JARVIS_SPEAK.speak import *


gesture_controller = None


def Function_cmd(text):
    global gesture_controller

    if "check internet speed" in text or "check speed test" in text or "speed test" in text:
        check_internet_speed()
    elif "are you there" in text or "hello there" in text:
        internet_status()
    elif "check temperature" in text or "temperature" in text:
        Temp()
    elif "find my ip" in text or "ip address" in text:
        speak("your ip is " + find_my_ip())
    elif "what is the time" in text or "time" in text or "what time is" in text:
        what_is_the_time()
    elif "start clap with music system" in text or "start smart music system" in text:
        speak("ok now starting")
        clap_to_music()
    elif text.startswith("content"):
        speak("Generating content for your topic.")
        generate_content_file(text)
    elif text.startswith("remember that"):
        info = text.replace("remember that", "").strip()
        remember(info)
        speak("Got it. I will remember that.")

    elif "gesture volume control" in text or "volume control" in text:
        if gesture_controller is None:
            gesture_controller = VolumeGestureController(speak_function=speak)
        gesture_controller.start()

    elif "what do you remember" in text or "show me your memory" in text:
        memories = recall_memory()
        if memories:
            speak("Here's what I remember:")
            for item in memories:
                speak(item)
        else:
            speak("I currently don't have any memory stored.")

    elif "forget everything" in text or "clear your memory" in text:
        forget_all()
        speak("All memory has been cleared.")

    else:
        response = normal_chat.llm_chat(text)
        if response:
            speak(response)


if __name__ == "__main__":
    Function_cmd("gesture volume control")