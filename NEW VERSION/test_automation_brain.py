# Path: d:\New folder (2) - JARVIS\test_automation_brain.py
# test_automation_brain.py
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from core.brain.model import JarvisBrain

def test_brain():
    brain = JarvisBrain()
    queries = [
        "send email to rahul, hello there",
        "post on twitter, jarvis is live now",
        "instagram pe post karo, checking automation",
        "send whatsapp to shivang, how are you",
        "mail kar do rahul ko subject urgent"
    ]
    
    print("Testing AI Brain Automation Intent Prediction...")
    for q in queries:
        intent, confidence = brain.predict(q)
        print(f"Query: '{q}' -> Intent: {intent} ({confidence:.2f})")

if __name__ == "__main__":
    test_brain()
