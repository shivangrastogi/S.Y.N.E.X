from AUTOMATION.COMMON_AUTOMATION.close import *
from AUTOMATION.COMMON_AUTOMATION.open import *
from UTILS.tts_singleton import speak

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
        speak("Closing Now.")
        close()
