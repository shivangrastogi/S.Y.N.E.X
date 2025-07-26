import datetime
<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import *


=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)

def what_is_the_time():
    try:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {current_time}")

    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(error_message)
        speak(error_message)
