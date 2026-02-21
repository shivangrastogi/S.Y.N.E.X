from BACKEND.core.brain.state_manager import StateManager, AudioState
from BACKEND.core.listener.voice_listener import VoskListener
from BACKEND.core.speaker.speech_service import SpeechService
import time


def main():
    # ---------- State Manager ----------
    state_manager = StateManager()
    state_manager.set_state(AudioState.LISTENING)

    # ---------- Listener ----------
    listener = VoskListener(
        model_path="DATA/models/vosk/vosk-model-en",
        state_manager=state_manager
    )
    listener.start_listening()

    # ---------- Speaker ----------
    speech = SpeechService(state_manager)

    # ---------- Startup ----------
    speech.speak("Jarvis audio loop test started. Please speak.")

    time.sleep(1)

    # ---------- Listen → Speak Loop ----------
    while True:
        text = listener.listen_once()
        if not text:
            continue

        print("[HEARD]:", text)

        # Speak exactly what was heard
        speech.speak(text)


if __name__ == "__main__":
    main()
