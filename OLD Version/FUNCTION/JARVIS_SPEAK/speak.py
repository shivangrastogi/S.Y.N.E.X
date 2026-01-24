import os
import time
from TTS.api import TTS
import playsound

class JarvisSpeaker:
    def __init__(self, model_name="tts_models/en/ljspeech/fast_pitch", device="cpu"):
        # Initialize your offline TTS model once here
        self.tts = TTS(model_name=model_name).to(device)

    def speak(self, text="Hello", file_path=None):
        if not text:
            return  # Do nothing if text is empty or None
        print("Speaking :", text)

        # Use unique filename if not provided
        if file_path is None:
            filename = f"output_{int(time.time() * 1000)}.wav"
            file_path = os.path.join("outputs", filename)

        # Ensure output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        try:
            # Generate and save audio locally
            self.tts.tts_to_file(text=text, file_path=file_path)
        except PermissionError as e:
            print(f"PermissionError writing TTS file: {e}")
            raise

        # Convert Windows-style path to forward slashes for playsound compatibility
        abs_path = os.path.abspath(file_path).replace("\\", "/")

        # Play the saved audio file
        playsound.playsound(abs_path)
