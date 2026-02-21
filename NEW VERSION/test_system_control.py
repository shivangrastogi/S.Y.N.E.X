# Path: d:\New folder (2) - JARVIS\test_system_control.py
# test_system_control.py
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

# Mock Synex and other dependencies
class MockSynex:
    def __init__(self):
        self.speaker = type('obj', (object,), {'speak': lambda self, msg: print(f"JARVIS Speaking: {msg}")})()
    def set_gesture_allowed(self, val): pass

from command_processor import CommandProcessor

def test_system_flow():
    synex = MockSynex()
    processor = CommandProcessor(synex)
    
    queries = [
        "mute my laptop",
        "volume up",
        "volume kam karo",
        "increase brightness",
        "screen ki brightness badhao",
        "unmute volume"
    ]
    
    print("Testing System Control Flow...")
    for q in queries:
        # Check intent prediction first
        intent, confidence = processor.brain.predict(q)
        print(f"Query: '{q}' -> Intent: {intent} ({confidence:.2f})")
        
        # Process and get response
        response = processor.process(q)
        print(f"Response: {response}\n")

if __name__ == "__main__":
    test_system_flow()
