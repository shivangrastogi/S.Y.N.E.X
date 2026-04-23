import os
import asyncio
import threading
import time
import pygame
import edge_tts
import pyttsx3

class TTS:
    def __init__(self, voice="en-IN-NeerjaNeural"):
        self.voice = voice
        self.rate = "+0%"
        self.pitch = "+0Hz"
        
        # Audio cache
        self.audio_dir = "data/audio_cache"
        os.makedirs(self.audio_dir, exist_ok=True)
        self.temp_file = os.path.join(self.audio_dir, "speech.mp3")
        
        # Initialize pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            
        # Offline fallback
        self.offline_engine = pyttsx3.init()

    def speak(self, text):
        """
        Speaks the text using Edge-TTS (online) or pyttsx3 (offline).
        """
        print(f"Jarvis: {text}")
        
        # Try Online TTS (Edge-TTS)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._generate_audio(text))
            loop.close()
            
            # Play using pygame
            pygame.mixer.music.load(self.temp_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
            
        except Exception as e:
            # Fallback to Offline TTS
            print(f"Online TTS failed, using offline fallback: {e}")
            self.offline_engine.say(text)
            self.offline_engine.runAndWait()

    async def _generate_audio(self, text):
        communicate = edge_tts.Communicate(
            text, 
            self.voice,
            rate=self.rate,
            pitch=self.pitch
        )
        await communicate.save(self.temp_file)

if __name__ == "__main__":
    # Quick test
    tts = TTS()
    tts.speak("Hello, this is Jarvis. Main Hinglish bol sakta hoon.")
