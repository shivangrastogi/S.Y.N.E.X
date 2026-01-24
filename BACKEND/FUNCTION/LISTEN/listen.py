# listen.py
import os
import queue
import json
import time
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from colorama import Fore, Style, init as colorama_init
from datetime import datetime
from FUNCTION.SPEAK.speak import is_speaking

colorama_init(autoreset=True)

# Use relative path from BACKEND directory
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BACKEND_DIR, "DATA", "LISTEN MODAL", "Vosk Modal", "vosk-model-small-en-us-0.15")
SAMPLE_RATE = 16000
BLOCKSIZE = 8000
TIMEOUT_SEC = 10
MAX_SILENCE = 12

if not os.path.isdir(MODEL_PATH):
    raise FileNotFoundError(f"Vosk model not found at {MODEL_PATH}")
model = Model(MODEL_PATH)

def now():
    return datetime.now().strftime("%H:%M:%S")

def listen():
    q = queue.Queue()

    def callback(indata, frames, time_, status):
        if status:
            print(Fore.RED + f"Audio error: {status}" + Style.RESET_ALL)
        q.put(bytes(indata))

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCKSIZE,
                           dtype='int16', channels=1, callback=callback):
        rec = KaldiRecognizer(model, SAMPLE_RATE)
        silence = 0
        printed_listen = False
        partial = ""
        last_state = None  # "speaking" or "listening"

        while True:
            # Show "speaking" status
            if is_speaking():
                if last_state != "speaking":
                    print(Fore.MAGENTA + f"🔇 Speaking..." + Style.RESET_ALL)
                    last_state = "speaking"
                time.sleep(0.05)
                continue

            # Show "listening" status
            if last_state != "listening":
                print(Fore.CYAN + f"\r🟢 Listening..." + Style.RESET_ALL, end="")
                last_state = "listening"

            try:
                data = q.get(timeout=TIMEOUT_SEC)
            except queue.Empty:
                silence += 1
                if silence >= MAX_SILENCE:
                    print(Fore.RED + f"\r⏱️ Timeout — no speech detected." + Style.RESET_ALL)
                    return ""
                continue

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text:
                    print(Fore.RESET + f"\r🎙️ You: {text}" + Style.RESET_ALL)
                    return text
            else:
                new_partial = json.loads(rec.PartialResult()).get("partial", "")
                if new_partial and new_partial != partial:
                    partial = new_partial
                    # Replace line dynamically with partial speech
                    print(Fore.YELLOW + f"\r... {partial}" + Style.RESET_ALL, end="")

# For testing
if __name__ == "__main__":
    while True:
        text = listen()
        if text:
            print("✅ Recognized:", text)
        else:
            print("❌ Nothing detected.")
        time.sleep(1)
