import json
import os

class StateManager:
    def __init__(self, intents_path='data/intents.json'):
        self.intents_path = intents_path
        self.current_state = {
            "intent": None,
            "slots": {},
            "is_waiting": False,
            "waiting_for": None
        }
        self.load_intents()

    def load_intents(self):
        with open(self.intents_path, 'r') as f:
            self.intents_data = json.load(f)

    def process_prediction(self, prediction, extracted_entities):
        """
        Takes the neural prediction and current extracted entities to decide 
        if we can execute or need to ask for more info.
        """
        if not prediction:
            return "Sorry, I didn't understand that."

        intent_name = prediction[0]['intent']
        intent_config = self.intents_data.get(intent_name)

        if not intent_config:
            return "Intent configuration missing."

        # Initialize the state for the new intent
        self.current_state["intent"] = intent_name
        self.current_state["slots"].update(extracted_entities)

        # Check for missing required entities
        required = intent_config.get("required_entities", [])
        for entity in required:
            if entity not in self.current_state["slots"] or not self.current_state["slots"][entity]:
                self.current_state["is_waiting"] = True
                self.current_state["waiting_for"] = entity
                return intent_config["prompts"].get(entity, f"Please provide the {entity}.")

        # If all slots are filled
        self.current_state["is_waiting"] = False
        self.current_state["waiting_for"] = None
        
        # Capture intent before reset
        final_intent = intent_name
        final_slots = self.current_state["slots"].copy()
        
        # Reset state after capturing
        self.reset_state()
        
        return f"SUCCESS_EXECUTE|{final_intent}|{json.dumps(final_slots)}"

    def handle_follow_up(self, user_input):
        """
        If we were waiting for a specific entity, treat this input as that entity.
        """
        if self.current_state["is_waiting"]:
            entity_name = self.current_state["waiting_for"]
            self.current_state["slots"][entity_name] = user_input
            
            # Re-process with the new data
            return self.process_prediction([{"intent": self.current_state["intent"]}], self.current_state["slots"])
        
        return None

    def execute_intent(self, intent, slots):
        # Deprecated: Handled by main_engine and executor
        pass


    def reset_state(self):
        self.current_state = {
            "intent": None,
            "slots": {},
            "is_waiting": False,
            "waiting_for": None
        }

if __name__ == "__main__":
    sm = StateManager()
    
    # Test Case 1: Incomplete Command
    print("User: Schedule a meeting")
    # Simulation: Neural Engine predicts 'schedule_meeting', but no entities found
    response = sm.process_prediction([{"intent": "schedule_meeting"}], {})
    print(f"Jarvis: {response}")
    
    # Follow-up
    print("User: Shivang")
    response = sm.handle_follow_up("Shivang")
    print(f"Jarvis: {response}")
    
    # Second Follow-up
    print("User: 5 PM")
    response = sm.handle_follow_up("5 PM")
    print(f"Jarvis: {response}")
