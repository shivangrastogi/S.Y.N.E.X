# Path: d:\New folder (2) - JARVIS\test_automation_full.py
# test_automation_full.py
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

# Mock Synex and other dependencies if needed
class MockSynex:
    def __init__(self):
        self.speaker = type('obj', (object,), {'speak': lambda self, msg: print(f"JARVIS Speaking: {msg}")})()
    def set_gesture_allowed(self, val): pass

from command_processor import CommandProcessor

def test_full_flow():
    synex = MockSynex()
    processor = CommandProcessor(synex)
    
    queries = [
        "send whatsapp to Rahul, Hello there",
        "send email to John, please check the report",
        "post to twitter, JARVIS is now automated!",
        "post to instagram, Loving the new UI",
        "mail kar do rahul ko subject urgent"
    ]
    
    print("Testing Full Command Processor Flow with Automation...")
    for q in queries:
        response = processor.process(q)
        print(f"Query: '{q}'\nResponse: {response}\n")

if __name__ == "__main__":
    test_full_flow()
