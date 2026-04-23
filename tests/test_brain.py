import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.normalizer import HinglishNormalizer
from core.intent_engine import IntentEngine

def test_brain():
    print("--- Jarvis v3.0 Brain Test ---")
    normalizer = HinglishNormalizer()
    engine = IntentEngine()
    
    test_cases = [
        "bhai chrome open kar de",
        "chrome kholo please",
        "notepad band karo",
        "mausam batao",
        "play some music please",
        "battery check karo"
    ]
    
    print(f"{'Original':<30} | {'Normalized':<20} | {'Intent':<15} | {'Score'}")
    print("-" * 80)
    
    for original in test_cases:
        normalized = normalizer.normalize(original)
        intent, score = engine.get_intent(normalized)
        
        print(f"{original:<30} | {normalized:<20} | {intent:<15} | {score:.1f}")

if __name__ == "__main__":
    test_brain()
