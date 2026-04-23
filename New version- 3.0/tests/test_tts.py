import sys
import os

# Add the project root to sys.path to allow importing from 'core'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.tts import TTS

def test_speech():
    print("Initializing TTS Test...")
    engine = TTS()
    
    test_phrases = [
        "System is online.",
        "A.E.R.I.S version 3.0 ready for deployment.",
        "Bhai, chrome kholo.",  # Testing Hinglish phonetic output
        "Everything looks good."
    ]
    
    for phrase in test_phrases:
        print(f"Testing phrase: {phrase}")
        engine.speak(phrase)

if __name__ == "__main__":
    test_speech()
