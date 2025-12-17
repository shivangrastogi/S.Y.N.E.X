# BACKEND/CORE/Utils/AudioTools.py
# Echo cancellation and audio utilities

import numpy as np
import threading


class EchoCanceller:
    def __init__(self):
        self.audio_history = []
        self.max_history = 5  # Keep last 5 audio chunks
        self.history_lock = threading.Lock()

    def add_played_audio(self, audio_data):
        """Add audio that was played to history for cancellation"""
        with self.history_lock:
            self.audio_history.append(audio_data.copy())
            if len(self.audio_history) > self.max_history:
                self.audio_history.pop(0)

    def cancel_echo(self, input_audio):
        """Simple echo cancellation using played audio history"""
        with self.history_lock:
            if not self.audio_history:
                return input_audio

            # Use the most recent played audio for cancellation
            reference = self.audio_history[-1]
            min_len = min(len(input_audio), len(reference))

            if min_len == 0:
                return input_audio

            # Simple subtraction (real implementations use adaptive filters)
            try:
                cancelled = np.subtract(
                    input_audio[:min_len].astype(np.float32),
                    reference[:min_len].astype(np.float32) * 0.3
                )
                return np.clip(cancelled, -32768, 32767).astype(np.int16)
            except:
                return input_audio


# Global echo canceller instance
echo_canceller = EchoCanceller()


def is_jarvis_self_talk(text: str) -> bool:
    """Detect if the text matches common Jarvis responses"""
    jarvis_patterns = [
        "yes sir", "sir", "jarvis", "searching", "opening",
        "i'm sorry", "apologies", "according to", "here is",
        "initializing", "welcome", "hello sir", "hey there",
        "i found", "let me", "i'll", "right away"
    ]
    if not text:
        return False
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in jarvis_patterns)