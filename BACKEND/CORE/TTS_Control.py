# BACKEND/TTS_Control.py (REVISED NON-BLOCKING VERSION)

import time
import pyttsx3
import random
import sys
from queue import Queue, Empty
import threading

# --- Global Initialization ---
engine = None
try:
    # IMPORTANT: Initialize without starting the loop yet.
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')

    MALE_VOICE_ID = next((v.id for v in voices if 'male' in str(v.gender).lower() or 'david' in v.name.lower()),
                         voices[0].id)
    engine.setProperty('voice', MALE_VOICE_ID)
    engine.setProperty('rate', 180)

    # Custom property to track speaking state globally
    _is_speaking_event = threading.Event()


    # Define callbacks to manage the speaking state event
    def on_start(name):
        _is_speaking_event.set()  # Set the flag when speech starts


    def on_end(name, completed):
        _is_speaking_event.clear()  # Clear the flag when speech ends


    engine.connect('started-utterance', on_start)
    engine.connect('finished-utterance', on_end)


except Exception as e:
    print(f"❌ TTS INIT ERROR: Failed to load pyttsx3: {e}")
    engine = None
    _is_speaking_event = None  # Ensure this is safe if engine is None


# --- Dedicated Thread Class for pyttsx3 ---
# This thread *only* runs the engine's startLoop() and handles queue dispatch.

class TtsWorker(threading.Thread):
    def __init__(self, engine):
        super().__init__(daemon=True)
        self.engine = engine
        self.queue = Queue()
        self.running = True
        self.start()

    def run(self):
        """This runs the pyttsx3 event loop."""
        if self.engine:
            self.engine.startLoop()  # This is the *main blocking call* now

        # NOTE: startLoop() must be terminated by engine.stop() called from
        # *another* thread.

    def stop_engine_loop(self):
        """Called by JarvisSpeaker.shutdown() to stop the engine's blocking loop."""
        self.running = False
        if self.engine:
            self.engine.stop()

    def dispatch_command(self, text, interrupt):
        """Called by JarvisSpeaker.speak()"""
        if interrupt:
            # For non-blocking mode, stop the queue and the current speech
            self.engine.stop()
            # Re-initialize the engine after a hard stop/interrupt sometimes helps stability
            # But let's rely on stop() for now.

        # Use a small delay after a stop to ensure the engine is ready for a new command
        time.sleep(0.01)

        self.engine.say(text)

        # IMPORTANT: Run the loop once to execute the queued say() call if it isn't running
        # This is a key hack if the engine's main loop isn't responsive.
        # However, since startLoop() is blocking our run(), we must only call say().

        # If the worker thread is running the loop, say() alone should suffice.


class JarvisSpeaker:
    _instance = None

    def __new__(cls):
        if not cls._instance and engine:
            cls._instance = super(JarvisSpeaker, cls).__new__(cls)
            # Worker is now responsible for starting/running the engine loop
            cls._instance.worker = TtsWorker(engine)

        return cls._instance

    def speak(self, text, interrupt=False):
        """Delegates the command to the worker's dispatcher."""
        if not self._instance or not self._instance.worker:
            print(f"JARVIS (Queue Failed): {text}")
            return

        if text and text.strip():
            # Delegate to the worker to handle the engine calls
            self._instance.worker.dispatch_command(text, interrupt)

    def is_speaking(self):
        """Checks the global event set by the engine's native callbacks."""
        return _is_speaking_event.is_set()

    def shutdown(self):
        if self._instance and self._instance.worker:
            self._instance.worker.stop_engine_loop()
            self._instance.worker.join(timeout=1.0)
            print("TTS Engine Shutdown Complete.")


# --- Compatibility Functions remain the same, relying on JarvisSpeaker.is_speaking() ---

def speak(text, interrupt=False):
    speaker_instance = JarvisSpeaker()
    if speaker_instance:
        speaker_instance.speak(text, interrupt)


def is_speaking():
    speaker_instance = JarvisSpeaker()
    if speaker_instance:
        return speaker_instance.is_speaking()
    return False


# wait_for_speech_complete is no longer needed since we aren't using a Queue in the same way.
# We will use the built-in is_speaking check.
def wait_for_speech_complete(timeout=1.0):
    speaker_instance = JarvisSpeaker()
    if not speaker_instance:
        return True

    start_time = time.time()
    # Wait for the native pyttsx3 speaking event to clear
    while speaker_instance.is_speaking():
        if time.time() - start_time > timeout:
            return False
        time.sleep(0.1)
    return True