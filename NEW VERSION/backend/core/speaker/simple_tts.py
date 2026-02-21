#!/usr/bin/env python3
"""
Simple TTS using pyttsx3 in subprocess mode.
This avoids pyttsx3's threading and locking issues.
"""
import sys
import os

# Suppress any Qt warnings
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

def speak(text):
    """Speak text using pyttsx3"""
    try:
        import pyttsx3
        
        # Create fresh engine instance
        engine = pyttsx3.init("sapi5")
        engine.setProperty("rate", 180)
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[0].id)
        
        engine.say(text)
        engine.runAndWait()
        
        # Explicitly clean up
        del engine
        
        print("SUCCESS", flush=True)
        return 0
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: simple_tts.py <text>", flush=True)
        sys.exit(1)
    
    text = " ".join(sys.argv[1:])
    sys.exit(speak(text))
