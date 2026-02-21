# Path: d:\New folder (2) - JARVIS\backend\core\speech\speaker.py
"""
Speaker Module - Text-to-Speech Engine
Handles text-to-speech synthesis using Microsoft Edge TTS.
"""

import edge_tts
import pygame
import asyncio
import os


class SpeakEngine:
    def __init__(self):
        self.output_file = "response.mp3"
        # Using Microsoft Edge TTS voices
        # hi-IN-MadhurNeural: Deep male Hindi voice
        # en-US-ChristopherNeural: Proper deep, professional male English voice
        self.hindi_voice = "hi-IN-MadhurNeural"
        self.english_voice = "en-US-ChristopherNeural"
        
        # Higher buffer (2048) to reduce CPU overhead
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)



    async def speak(self, text, language="hi"):
        """
        Synthesizes text to speech using edge-tts and plays it.
        """
        print(f"Speaking ({language}): {text}")
        voice = self.hindi_voice if language == "hi" else self.english_voice
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(self.output_file)
        
        try:
            pygame.mixer.music.load(self.output_file)
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Unload instead of quit for faster next playback
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Error playing audio: {e}")
            
        # Clean up the file
        try:
            if os.path.exists(self.output_file):
                os.remove(self.output_file)
        except PermissionError:
            pass  # Sometimes file is still locked briefly
