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
