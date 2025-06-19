from AUTOMATION.COMMON_AUTOMATION.close import *
from AUTOMATION.COMMON_AUTOMATION.open import *


def common_cmd(text):
    text = text.lower().strip()

    # Close commands that imply closing an app or window
    close_keywords = [
        "close this", "close window", "close application",
        "close app", "band kar do", "band karo", "close the program", "close"
    ]

    # Open command for applications (not websites!)
    if text.startswith("open "):
        if "website" in text or "site" in text:
            # Let google_cmd handle websites
            pass
        else:
            app_name = text.replace("open", "").strip()
            if app_name:
                open(app_name)

    # Confirm before closing general apps/windows
    elif any(keyword in text for keyword in close_keywords):
        speak("Are you sure you want to close this application? Please say yes or no.")
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            try:
                audio = recognizer.listen(source, timeout=5)
                response = recognizer.recognize_google(audio).lower()
                if "yes" in response:
                    close()
                else:
                    speak("Closing cancelled.")
            except:
                speak("I didn't catch that. Closing cancelled.")




# def common_cmd(text):
#     if "close" in text or "band kar do" in text:
#         close()
#     else:
#         pass
#
