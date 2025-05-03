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



# import speech_recognition as sr
# import os
# import threading
# from mtranslate import translate
# from colorama import Fore, Style, init
#
# init(autoreset=True)
#
# def print_loop():
#     while True:
#         print(Fore.LIGHTGREEN_EX + "I am Listening...",end="",flush=True)
#         print(Style.RESET_ALL,end="",flush=True)
#         print("",end="",flush=True)
#
# def Trans_hindi_to_english(txt):
#     english_txt = translate(txt,"en-us")
#     return english_txt
#
# def listen():
#     recognizer = sr.Recognizer()
#     recognizer.dynamic_energy_threshold = False
#     recognizer.energy_threshold = 34000
#     recognizer.dynamic_energy_adjustment_damping = 0.010
#     recognizer.dynamic_energy_ratio = 1.0
#     recognizer.pause_threshold = 0.3
#     recognizer.operation_timeout = None
#     recognizer.pause_threshold = 0.2
#     recognizer.non_speaking_duration = 0.2
#
#     with sr.Microphone() as source:
#         recognizer.adjust_for_ambient_noise(source)
#         while True:
#             print(Fore.LIGHTGREEN_EX + "I am Listening...",end="",flush=True)
#             try:
#                 audio = recognizer.listen(source, timeout = None)
#                 print("\r"+Fore.LIGHTYELLOW_EX+ "Got it , Now Recognizing...",end="",flush=True)
#                 # recognized_txt = recognizer.recognize_google(audio).lower()
#                 recognized_txt = recognizer.recognize_google(audio, language='hi').lower()
#
#                 if recognized_txt:
#                     translated_txt = Trans_hindi_to_english(recognized_txt)
#                     print("\r" +Fore.BLUE + "Mr TONY : " + translated_txt)
#                     return translated_txt
#                 else:
#                     return ""
#             except sr.UnknownValueError:
#                 recognized_txt=""
#             finally:
#                 print("\r",end="",flush=True)
#
#         os.system("cls" if os.name == "nt" else "clear")
#         listen_thread = threading.Thread(target=listen)
#         print_thread = threading.Thread(target=print_loop)
#         listen_thread.start()
#         print_thread.start()
#         listen_thread.join()
#         print_thread.join()
#
# def hearing():
#     recognizer = sr.Recognizer()
#     recognizer.dynamic_energy_threshold = False
#     recognizer.energy_threshold = 34500
#     recognizer.dynamic_energy_adjustment_damping = 0.011
#     recognizer.dynamic_energy_ratio = 1.9
#     recognizer.pause_threshold = 0.3
#     recognizer.operation_timeout = None
#     recognizer.pause_threshold = 0.2
#     recognizer.non_speaking_duration = 0.2
#
#     with sr.Microphone() as source:
#         recognizer.adjust_for_ambient_noise(source)
#         while True:
#             try:
#                 audio = recognizer.listen(source, timeout = None)
#                 recognized_txt = recognizer.recognize_google(audio).lower()
#                 if recognized_txt:
#                     translated_txt = Trans_hindi_to_english(recognized_txt)
#                     return translated_txt
#                 else:
#                     return ""
#             except sr.UnknownValueError:
#                 recognized_txt=""
#             finally:
#                 print("\r",end="",flush=True)
