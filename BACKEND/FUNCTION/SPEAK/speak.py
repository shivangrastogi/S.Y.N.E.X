# speak.py
import os
import time
import threading
import hashlib
import simpleaudio as sa
from queue import Queue
from BRAIN.tts_engine import TTSEngine

# --- Globals ---
_AUDIO_CACHE = {}
_CACHE_LOCK = threading.Lock()
speech_queue = Queue()
stop_signal = threading.Event()
speaking_flag = threading.Event()

def is_speaking():
    return speaking_flag.is_set()

# --- Main Speaker Class ---
class JarvisSpeaker:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(JarvisSpeaker, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self.engine = TTSEngine()
        threading.Thread(target=self._worker, daemon=True).start()

    def speak(self, text, interrupt=False):
        if not text.strip():
            return
        if interrupt:
            stop_signal.set()
            with speech_queue.mutex:
                speech_queue.queue.clear()
            stop_signal.clear()
        speech_queue.put(text)

    def stop(self):
        stop_signal.set()

    # --- Private Methods ---
    def _cache_audio(self, text):
        key = hashlib.md5(text.encode()).hexdigest()
        with _CACHE_LOCK:
            if key in _AUDIO_CACHE and os.path.exists(_AUDIO_CACHE[key]):
                return _AUDIO_CACHE[key]

        wav = self.engine.synthesize(text)
        if wav is None:
            return None

        os.makedirs("FUNCTION/SPEAK/outputs", exist_ok=True)
        path = os.path.join("FUNCTION", "SPEAK", "outputs", f"tts_{key}.wav")
        self.engine.save(wav, path)
        with _CACHE_LOCK:
            _AUDIO_CACHE[key] = path
        return path

    def _play_audio(self, wav_path):
        try:
            wave = sa.WaveObject.from_wave_file(wav_path)
            play_obj = wave.play()
            speaking_flag.set()
            while play_obj.is_playing():
                if stop_signal.is_set():
                    play_obj.stop()
                    break
                time.sleep(0.02)
        except Exception as e:
            print(f"Playback error: {e}")
        finally:
            speaking_flag.clear()

    def _worker(self):
        while True:
            text = speech_queue.get()
            if text:
                wav_path = self._cache_audio(text)
                if wav_path:
                    self._play_audio(wav_path)
            speech_queue.task_done()

# --- Testing ---
if __name__ == "__main__":
    speaker = JarvisSpeaker()
    while True:
        speaker.speak("Hello Shivang, testing your new Jarvis speaker system.")
        while is_speaking():
            time.sleep(0.1)
        print("✅ Done speaking. Looping again.\n")
        time.sleep(2)
