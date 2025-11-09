import os
import threading
from vosk import Model
from BRAIN.tts_engine import TTSEngine  # Assuming this is your TTS engine path

# ✅ Your permanent local Vosk model path
VOSK_MODEL_PATH = r"C:\Users\bosss\PycharmProjects\PythonProject\jarvis\PythonProject3\BACKEND\DATA\LISTEN MODAL\Vosk Modal\vosk-model-small-en-us-0.15"

class JarvisEngineManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(JarvisEngineManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        self.vosk_model = None
        self.tts_engine = None
        self.models_loaded = threading.Event()
        self.loading_thread = None

    def load_models_async(self):
        """Starts loading models in a background thread."""
        if not self.models_loaded.is_set() and (self.loading_thread is None or not self.loading_thread.is_alive()):
            print("Starting background model loading...")
            self.loading_thread = threading.Thread(target=self._load_all_models, daemon=True)
            self.loading_thread.start()

    def _load_all_models(self):
        try:
            # 1. Load Vosk Model
            print(f"Loading Vosk model from: {VOSK_MODEL_PATH}")
            if not os.path.isdir(VOSK_MODEL_PATH):
                raise FileNotFoundError(f"❌ Vosk model not found at: {VOSK_MODEL_PATH}")

            self.vosk_model = Model(VOSK_MODEL_PATH)
            print("✅ Vosk model loaded successfully.")

            # 2. Load TTS Engine
            print("Loading TTS engine...")
            self.tts_engine = TTSEngine()
            print("✅ TTS Engine loaded successfully.")

            self.models_loaded.set()
            print("✅ All models loaded successfully.")
        except Exception as e:
            print(f"Error loading models: {e}")
            self.models_loaded.clear()

    def is_models_loaded(self):
        return self.models_loaded.is_set()

    def get_vosk_model(self):
        if not self.is_models_loaded():
            raise RuntimeError("Vosk model is not loaded yet.")
        return self.vosk_model

    def get_tts_engine(self):
        if not self.is_models_loaded():
            raise RuntimeError("TTS Engine is not loaded yet.")
        return self.tts_engine


engine_manager = JarvisEngineManager()
