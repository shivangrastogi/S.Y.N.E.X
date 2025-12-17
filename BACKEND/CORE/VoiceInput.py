# CORE/VoiceInput.py
import speech_recognition as sr
from mtranslate import translate
from colorama import Fore, init

init(autoreset=True)

def Trans_hindi_to_english(txt):
    try:
        english_txt = translate(txt, "en-us")
        return english_txt
    except Exception as e:
        print(Fore.RED + f"Translation Error: {e}")
        return txt  # Fallback to original

def listen():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 3000  # You can tune this
    recognizer.pause_threshold = 0.5
    recognizer.non_speaking_duration = 0.3

    with sr.Microphone() as source:
        print(Fore.LIGHTGREEN_EX + "I am Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=6)
            print(Fore.LIGHTYELLOW_EX + "Got it, Recognizing...")

            recognized_txt = recognizer.recognize_google(audio, language='hi-IN').lower()

            if recognized_txt:
                translated_txt = Trans_hindi_to_english(recognized_txt)
                print(Fore.BLUE + "Mr TONY: " + translated_txt)
                return translated_txt
            else:
                return ""

        except sr.WaitTimeoutError:
            print(Fore.RED + "Listening timed out. No speech detected.")
            return ""

        except sr.UnknownValueError:
            print(Fore.RED + "Could not understand audio.")
            return ""

        except sr.RequestError as e:
            print(Fore.RED + f"API error: {e}")
            return ""

def hearing():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 3000  # Adjust this if needed
    recognizer.pause_threshold = 0.5
    recognizer.non_speaking_duration = 0.3

    with sr.Microphone() as source:
        print(Fore.LIGHTGREEN_EX + "Awaiting Wake Word...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        try:
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=5)
            recognized_txt = recognizer.recognize_google(audio, language='hi-IN').lower()

            if recognized_txt:
                translated_txt = Trans_hindi_to_english(recognized_txt)
                print(Fore.CYAN + f"Wake Command Heard: {translated_txt}")
                return translated_txt
            else:
                return ""

        except sr.WaitTimeoutError:
            print(Fore.RED + "Wake word listening timed out.")
            return ""

        except sr.UnknownValueError:
            print(Fore.RED + "Didn't catch that.")
            return ""

        except sr.RequestError as e:
            print(Fore.RED + f"API error: {e}")
            return ""