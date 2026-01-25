# BACKEND/core/speaker/speech_service.py
import queue
import threading
from BACKEND.core.speaker.tts_engine import TTSEngine


class SpeechService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SpeechService, cls).__new__(cls)
        return cls._instance

    def __init__(self, state_manager):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.tts = TTSEngine(state_manager)
        self.queue = queue.Queue()

        self.worker = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.worker.start()

    def _run(self):
        while True:
            text = self.queue.get()
            if text is None:
                self.queue.task_done()
                break
            try:
                self.tts.speak_blocking(text)
            except Exception as e:
                print(f"[SPEECH SERVICE ERROR] {e}")
            finally:
                self.queue.task_done()

    def speak(self, text: str):
        if not text or not str(text).strip():
            return
        self.queue.put(text)

    def interrupt(self):
        self.tts.stop()

    def shutdown(self):
        try:
            self.queue.put(None)
            if self.worker.is_alive():
                self.worker.join(timeout=2)
        except Exception:
            pass
