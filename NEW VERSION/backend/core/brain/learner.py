# Path: d:\New folder (2) - JARVIS\backend\core\brain\learner.py
import json
import os
from core.brain.model import JarvisBrain

class JarvisLearner:
    def __init__(self, brain: JarvisBrain, feedback_path="backend/core/brain/data/feedback.json"):
        self.brain = brain
        self.feedback_path = os.path.abspath(feedback_path)
        
        if not os.path.exists(self.feedback_path):
            with open(self.feedback_path, 'w') as f:
                json.dump([], f)

    def collect_feedback(self, text, suggested_intent):
        """Stores new data for future training"""
        with open(self.feedback_path, 'r') as f:
            data = json.load(f)
            
        data.append({"text": text, "intent": suggested_intent})
        
        with open(self.feedback_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Immediately 'reinforce' the brain
        self.brain.learn(text, suggested_intent)

    def handle_unknown(self, text):
        """
        The 'anything else method'. 
        In this implementation, it uses Google Search or a predefined heuristic
        to guess the intent, then stores it.
        """
        print(f"Seeking alternative solution for: {text}")
        
        # Simple heuristic 'teacher':
        # In a real app, you'd call a powerful LLM here.
        if "open" in text.lower() or "chalao" in text.lower() or "kholo" in text.lower():
            inferred_intent = "open_item"
        elif "close" in text.lower() or "band" in text.lower():
            inferred_intent = "close_item"
        elif "battery" in text.lower():
            inferred_intent = "check_battery"
        elif "net" in text.lower() or "speed" in text.lower():
            inferred_intent = "check_internet_speed"
        elif "time" in text.lower() or "samay" in text.lower():
            inferred_intent = "check_time"
        elif any(w in text.lower() for w in ["how", "are", "you", "who", "what", "name", "naam", "kaise"]):
            inferred_intent = "wellbeing" if "how" in text.lower() else "identity"
        else:
            inferred_intent = "google_search" 
            
        # Reinforce
        self.collect_feedback(text, inferred_intent)
        return inferred_intent
