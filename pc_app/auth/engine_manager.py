# auth/engine_manager.py
import os
import threading
from vosk import Model
from BRAIN.tts_engine import TTSEngine  # Assuming this is your TTS engine path

# Define your model path here
# MODEL_PATH = r"D:\OFFICIAL_JARVIS\Personal-Assistant\Backend\DATA\LISTEN MODAL\Vosk Modal\vosk-model-small-en-us-0.15"
MODEL_PATH = os.path.join(os.environ['APPDATA'], "JARVIS_MODELS")
# This is the full path to the Vosk model *folder*
VOSK_MODEL_PATH = os.path.join(MODEL_PATH, "vosk-model-small-en-us-0.15")

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
                raise FileNotFoundError(f"Vosk model not found at {VOSK_MODEL_PATH}. Please run setup.")

            self.vosk_model = Model(VOSK_MODEL_PATH)  # <-- Use new path
            print("Vosk model loaded.")

            # 2. Load TTS Engine
            print("Loading TTS engine...")
            self.tts_engine = TTSEngine()
            print("TTS Engine loaded.")

            self.models_loaded.set()
            print("✅ All models loaded successfully.")
        except Exception as e:
            print(f"Error loading models: {e}")
            # This is critical. If models fail, we must inform the user.
            # We can handle this in main_ui.py
            self.models_loaded.clear()  # Ensure it's marked as *not* loaded

    def is_models_loaded(self):
        """Check if the models are ready."""
        return self.models_loaded.is_set()

    def get_vosk_model(self):
        if not self.is_models_loaded():
            raise RuntimeError("Vosk model is not loaded yet.")
        return self.vosk_model

    def get_tts_engine(self):
        if not self.is_models_loaded():
            raise RuntimeError("TTS Engine is not loaded yet.")
        return self.tts_engine


# Create a single, global instance that all other files can import
engine_manager = JarvisEngineManager()