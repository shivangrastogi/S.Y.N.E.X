# BACKEND/core/speaker/tts_engine.py
import threading
import subprocess
import os
import sys
from BACKEND.core.brain.state_manager import AudioState


class TTSEngine:
    """
    Thread-safe TTS engine using subprocess to avoid pyttsx3 threading issues.
    """

    def __init__(self, state_manager):
        self.state_manager = state_manager
        self._lock = threading.Lock()
        self._is_speaking = False
        self.tts_script = os.path.join(
            os.path.dirname(__file__),
            "simple_tts.py"
        )
        print(f"[TTS] Using subprocess mode with script: {self.tts_script}")

    # -----------------------------
    # PUBLIC API
    # -----------------------------
    def speak_blocking(self, text: str):
        """Speak text using subprocess (avoids pyttsx3 threading issues)"""
        if not text or not text.strip():
            return

        with self._lock:
            try:
                self._is_speaking = True
                self.state_manager.set_state(AudioState.SPEAKING)
                print(f"[TTS] Speaking: {text[:50]}...")

                # Call simple_tts.py in a subprocess
                result = subprocess.run(
                    [sys.executable, self.tts_script, text],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode == 0:
                    print("[TTS] Speech completed")
                else:
                    print(f"[TTS ERROR] subprocess returned {result.returncode}")
                    if result.stderr:
                        print(f"[TTS] stderr: {result.stderr}")
                
            except subprocess.TimeoutExpired:
                print("[TTS ERROR] subprocess timeout")
            except Exception as e:
                print(f"[TTS ERROR] {type(e).__name__}: {e}")

            finally:
                self._is_speaking = False
                self.state_manager.set_state(AudioState.IDLE)

    def stop(self):
        """Stop speaking"""
        with self._lock:
            self._is_speaking = False
            self.state_manager.set_state(AudioState.IDLE)

    def is_speaking(self):
        return self._is_speaking
