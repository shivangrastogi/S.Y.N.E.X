import sys
import os
import time

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.stt import STT

def test_listening():
    print("Initializing STT Test...")
    # Using the relative path from the project root
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'models', 'vosk-model')
    
    stt_engine = STT(model_path=model_dir)
    
    # Wait a moment for background model loading
    time.sleep(1)
    
    print("Testing STT (Online Google en-IN with Vosk Fallback)...")
    print("Please say something (e.g., 'Hello Jarvis' or 'Open Chrome')...")
    text = stt_engine.listen()

    
    if text:
        print(f"\n[SUCCESS] I heard: '{text}'")
    else:
        print("\n[FAILED] No speech detected or error occurred.")

if __name__ == "__main__":
    test_listening()
