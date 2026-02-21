# BACKEND/core/listener/voice_listener.py
from BACKEND.core.listener.speech_listener import SpeechListener
from BACKEND.core.brain.state_manager import AudioState
from colorama import Fore

class VoiceListener:
    """
    Jarvis-compatible voice listener.
    Wraps SpeechListener.
    """

    def __init__(self, state_manager=None):
        self.speech = SpeechListener()
        self.state_manager = state_manager
        self._stopped = False

    def start_listening(self):
        self._stopped = False
        print(Fore.GREEN + "🎤 Voice listener ready (Hindi + English)")

    def listen_once(self):
        """
        Blocks until user speaks or timeout.
        Returns English text or None.
        """
        if self._stopped:
            return None

        if self.state_manager:
            self.state_manager.wait_for_mic()
            self.state_manager.set_state(AudioState.LISTENING)

        text = self.speech.listen()

        if not text:
            if self.state_manager and self.state_manager.state == AudioState.LISTENING:
                self.state_manager.set_state(AudioState.IDLE)
            return None

        # Interrupt TTS if user speaks
        if self.state_manager and self.state_manager.state == AudioState.SPEAKING:
            self.state_manager.interrupt()
            return None

        if self.state_manager and self.state_manager.state == AudioState.LISTENING:
            self.state_manager.set_state(AudioState.IDLE)

        return text

    def stop(self):
        self._stopped = True
