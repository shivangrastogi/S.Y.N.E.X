<<<<<<< HEAD
import speech_recognition as sr
import os
import threading
from mtranslate import translate
from colorama import Fore, init

init(autoreset=True)

def print_loop():
    while True:
        print(Fore.LIGHTGREEN_EX + "I am Listening...", end="",flush=True)
        print(Style.RESET_ALL,end="",flush=True)
        print("",end="",flush=True)

def Trans_hindi_to_english(txt):
    try:
        english_txt = translate(txt, "en-us")
        return english_txt
    except Exception as e:
        print(Fore.RED + f"Translation Error: {e}")
        return txt  # Fallback to original

def recognize_any(audio):
    # Try Hindi first, fallback to English
    for lang in ['hi-IN', 'en-IN']:
        try:
            return sr.Recognizer().recognize_google(audio, language=lang).lower()
        except sr.UnknownValueError:
            continue
    return ""

def configure_recognizer(threshold=34000, damping=0.010, ratio=1.0):
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = threshold
    recognizer.dynamic_energy_adjustment_damping = damping
    recognizer.dynamic_energy_ratio = ratio
    recognizer.pause_threshold = 0.2
    recognizer.operation_timeout = None
    recognizer.non_speaking_duration = 0.1
    return recognizer

def listen():
    recognizer = configure_recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)

        while True:
            print(Fore.LIGHTGREEN_EX + "I am Listening...",end="",flush=True)
            try:
                audio = recognizer.listen(source, timeout=None)
                print("\r" + Fore.LIGHTYELLOW_EX + "Got it, Now Recognizing...", end="",flush=True)
                # recognized_txt = recognizer.recognize_google(audio, language='hi-IN').lower()
                recognized_txt = recognize_any(audio)

                if recognized_txt:
                    translated_txt = Trans_hindi_to_english(recognized_txt)
                    print("\r"+Fore.BLUE + "Mr Shivang: " + translated_txt);
                    return translated_txt
                else:
                    print(Fore.RED + "Sorry, couldn't recognize.")
                    return ""

            except sr.UnknownValueError:
                print(Fore.RED + "Could not understand audio.")

            except Exception as e:
                print(Fore.RED + f"Error: {e}")
                return ""

            finally:
                print("\r",end="",flush=True)

        os.system("cls" if os.name == "nt" else "clear")
        listen_thread = threading.Thread(target=listen)
        print_thread = threading.Thread(target=print_loop)
        listen_thread.start()
        print_thread.start()
        listen_thread.join()
        print_thread.join()

def hearing():
    recognizer = configure_recognizer(34500, 0.011, 1.9)

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

        while True:
            print(Fore.LIGHTGREEN_EX + "Awaiting Wake Word...")
            try:
                audio = recognizer.listen(source, timeout=None)
                # recognized_txt = recognizer.recognize_google(audio, language='en-IN').lower()
                recognized_txt = recognize_any(audio)

                if recognized_txt:
                    translated_txt = Trans_hindi_to_english(recognized_txt)
                    print(Fore.CYAN + f"Wake Command Heard: {translated_txt}")
                    return translated_txt
                else:
                    return ""

            except sr.UnknownValueError:
                print(Fore.RED + "Didn't catch that.")
                return ""

            except sr.RequestError as e:
                print(Fore.YELLOW + "Offline mode not available. Please connect to internet.")

            except Exception as e:
                print(Fore.RED + f"Hearing Error: {e}")
                return ""

            finally:
                print("\r",end="",flush=True);
=======
import os
import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from colorama import Fore, Style, init as colorama_init
from datetime import datetime

from UTILS.ui_signal import send_to_ui_chatbox

colorama_init(autoreset=True)

MODEL_PATH = r"S:\Study things\JARVIS\JARVIS\JARVIS_WITH_NEWGUI\DATA\VOSK_MODELS\LISTEN_MODEL\vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000
TIMEOUT_SEC = 15    # Maximum silence before giving up

if not os.path.isdir(MODEL_PATH):
    raise FileNotFoundError(f"Vosk model not found at: {MODEL_PATH}")
vosk_model = Model(MODEL_PATH)

def now():
    # Returns a formatted timestamp for logs
    return datetime.now().strftime("%H:%M:%S")

def listen():
    print(Fore.CYAN + f"[{now()}] Ready to listen. Speak into the microphone!")
    q = queue.Queue()

    def audio_callback(indata, frames, time, status):
        if status:
            print(Fore.RED + f"Audio Device Error: {status}")
        q.put(bytes(indata))

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                               dtype='int16', channels=1, callback=audio_callback):
            rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            print(Fore.LIGHTGREEN_EX + "🟢 Listening... (Say something)")
            print(Fore.YELLOW + "⬤", end="", flush=True)
            last_result_time = datetime.now()
            partial_text = ""
            while True:
                try:
                    data = q.get(timeout=TIMEOUT_SEC)
                except queue.Empty:
                    print(Fore.RED + f"\n[{now()}] Timeout: No speech detected.")
                    return ""
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    recognized_txt = result.get("text", "").strip()
                    if recognized_txt:
                        print(Style.RESET_ALL + "\r" + Fore.BLUE + f"🔹 Mr Shivang: {recognized_txt}")
                        send_to_ui_chatbox("User", recognized_txt)
                        return recognized_txt
                    else:
                        print(Style.RESET_ALL + "\r" + Fore.RED + f"[{now()}] Sorry, couldn't recognize.")
                        return ""
                else:
                    # Show live partial result when speaking
                    partial = json.loads(rec.PartialResult()).get("partial", "")
                    if partial and partial != partial_text:
                        print(Style.RESET_ALL + "\r" + Fore.LIGHTYELLOW_EX + f"[... ] {partial}" + " " * 30, end="", flush=True)
                        partial_text = partial
    except Exception as exc:
        print(Fore.RED + f"\n[{now()}] Audio Error: {exc}")
        return ""


def hearing():
    print(Fore.CYAN + f"[{now()}] Waiting for wake word...")
    q = queue.Queue()

    def audio_callback(indata, frames, time, status):
        if status:
            print(Fore.RED + f"Audio Device Error: {status}")
        q.put(bytes(indata))

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                               dtype='int16', channels=1, callback=audio_callback):
            rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            while True:
                try:
                    data = q.get(timeout=TIMEOUT_SEC)
                except queue.Empty:
                    print(Fore.RED + f"\n[{now()}] Wake word timeout.")
                    return ""
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    recognized_txt = result.get("text", "").strip()
                    if recognized_txt:
                        print(Fore.CYAN + f"\n[{now()}] Wake Command Heard: {recognized_txt}")
                        return recognized_txt
                    else:
                        continue
    except Exception as exc:
        print(Fore.RED + f"\n[{now()}] Audio Error: {exc}")
        return ""
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)
