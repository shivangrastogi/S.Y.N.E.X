# BACKEND/core/brain/state_manager.py

import threading
from enum import Enum


class AudioState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class StateManager:
    def __init__(self):
        self.state = AudioState.IDLE

        # Controls microphone access
        self.mic_gate = threading.Event()
        self.mic_gate.set()

        # Used to interrupt speech if user talks
        self.interrupt_event = threading.Event()

    def set_state(self, state: AudioState):
        self.state = state

        if state == AudioState.SPEAKING:
            self.mic_gate.clear()
            self.interrupt_event.clear()

        elif state == AudioState.LISTENING:
            self.mic_gate.set()

        else:
            # Keep mic open unless explicitly speaking
            self.mic_gate.set()

    def wait_for_mic(self):
        self.mic_gate.wait()

    def interrupt(self):
        self.interrupt_event.set()

    def is_interrupted(self):
        return self.interrupt_event.is_set()

    def get_mode(self) -> str:
        return self.state.value

    def is_idle(self) -> bool:
        return self.state == AudioState.IDLE

    def is_listening(self) -> bool:
        return self.state == AudioState.LISTENING

    def is_speaking(self) -> bool:
        return self.state == AudioState.SPEAKING
