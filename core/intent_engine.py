import json
import os
from rapidfuzz import process, fuzz

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class IntentEngine:
    def __init__(self, intents_path=None):
        intents_path = intents_path or os.path.join(_ROOT, "data", "intents.json")
        self.intents_path = intents_path
        self.intents = {}
        self.load_intents()

    def load_intents(self):
        if os.path.exists(self.intents_path):
            with open(self.intents_path, 'r') as f:
                self.intents = json.load(f)
        else:
            print(f"Warning: {self.intents_path} not found.")

    def get_intent(self, text, threshold=70):
        if not text:
            return None, 0

        highest_score = 0
        detected_intent = None

        for intent_name, config in self.intents.items():
            patterns = config.get("patterns", []) if isinstance(config, dict) else config
            if not patterns:
                continue
            match = process.extractOne(text, patterns, scorer=fuzz.WRatio)
            if match and match[1] > highest_score:
                highest_score = match[1]
                detected_intent = intent_name

        if highest_score >= threshold:
            return detected_intent, highest_score
        return "unknown", highest_score

if __name__ == "__main__":
    engine = IntentEngine()
    test_queries = [
        "open chrome",
        "start browser",
        "what is the weather",
        "play some music",
        "battery status please"
    ]
    
    for query in test_queries:
        intent, score = engine.get_intent(query)
        print(f"Query: '{query}' -> Intent: {intent} (Score: {score})")
