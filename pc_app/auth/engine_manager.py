# auth/engine_manager.py
import os
import threading
from vosk import Model
from BRAIN.tts_engine import TTSEngine  # Assuming this is your TTS engine path

# Define model path using APPDATA for portability
MODEL_PATH = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "JARVIS_MODELS")
VOSK_MODEL_PATH = os.path.join(MODEL_PATH, "vosk-model-small-en-us-0.15")

# Fallback to local BACKEND directory if APPDATA model doesn't exist
if not os.path.isdir(VOSK_MODEL_PATH):
    try:
        # Try to find BACKEND directory relative to pc_app
        pc_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        backend_fallback = os.path.join(os.path.dirname(pc_app_dir), "BACKEND", "DATA", "LISTEN MODAL", "Vosk Modal", "vosk-model-small-en-us-0.15")
        if os.path.isdir(backend_fallback):
            VOSK_MODEL_PATH = backend_fallback
    except Exception:
        pass
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

<<<<<<< HEAD
            self.vosk_model = Model(VOSK_MODEL_PATH)
            print("✅ Vosk model loaded successfully.")
=======
            self.vosk_model = Model(VOSK_MODEL_PATH)  # <-- Use new path
            print("Vosk model loaded.")
>>>>>>> personal-repo/main

            # 2. Load TTS Engine
            print("Loading TTS engine...")
            self.tts_engine = TTSEngine()
<<<<<<< HEAD
            print("✅ TTS Engine loaded successfully.")
=======
            print("TTS Engine loaded.")
>>>>>>> personal-repo/main

            self.models_loaded.set()
            print("✅ All models loaded successfully.")
        except Exception as e:
            print(f"Error loading models: {e}")
<<<<<<< HEAD
            self.models_loaded.clear()

    def is_models_loaded(self):
=======
>>>>>>> personal-repo/main
            # This is critical. If models fail, we must inform the user.
            # We can handle this in main_ui.py
            self.models_loaded.clear()  # Ensure it's marked as *not* loaded

    def is_models_loaded(self):
        """Check if the models are ready."""
<<<<<<< HEAD
>>>>>>> jarvis-repo/main
=======
>>>>>>> personal-repo/main
        return self.models_loaded.is_set()

    def get_vosk_model(self):
        if not self.is_models_loaded():
            raise RuntimeError("Vosk model is not loaded yet.")
        return self.vosk_model

    def get_tts_engine(self):
        if not self.is_models_loaded():
            raise RuntimeError("TTS Engine is not loaded yet.")
        return self.tts_engine


<<<<<<< HEAD
<<<<<<< HEAD
engine_manager = JarvisEngineManager()
=======
# Create a single, global instance that all other files can import
engine_manager = JarvisEngineManager()
>>>>>>> jarvis-repo/main
=======
# Create a single, global instance that all other files can import
engine_manager = JarvisEngineManager()
>>>>>>> personal-repo/main
