import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StateManager:
    """
    Manages conversation state for multi-turn entity slot-filling.

    Flow:
      process_prediction()  →  checks required entities
                                ├─ missing entity  →  asks prompt, sets is_waiting=True
                                └─ all filled       →  returns SUCCESS_EXECUTE|intent|{slots}

      handle_follow_up()    →  called when is_waiting=True
                                fills next missing slot, calls process_prediction again
    """

    def __init__(self, intents_path: str = None):
        self.intents_path = intents_path or os.path.join(_ROOT, "data", "intents.json")
        self._reset()
        self.intents_data = self._load_intents()

    def _load_intents(self) -> dict:
        with open(self.intents_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _reset(self):
        self.current_state = {
            "intent": None,
            "slots": {},
            "is_waiting": False,
            "waiting_for": None,
        }

    # ------------------------------------------------------------------ #

    def process_prediction(self, prediction: list, extracted_entities: dict) -> str:
        if not prediction:
            return "Sorry, samajh nahi aaya."

        intent_name = prediction[0]["intent"]
        intent_config = self.intents_data.get(intent_name)

        if not intent_config:
            return f"Intent '{intent_name}' ki configuration missing hai."

        self.current_state["intent"] = intent_name
        self.current_state["slots"].update(extracted_entities)

        # Check each required entity in order
        for entity in intent_config.get("required_entities", []):
            val = self.current_state["slots"].get(entity)
            if not val:
                self.current_state["is_waiting"] = True
                self.current_state["waiting_for"] = entity
                prompt = intent_config["prompts"].get(entity, f"Please provide the {entity}.")
                return prompt

        # All slots are filled — ready to execute
        self.current_state["is_waiting"] = False
        self.current_state["waiting_for"] = None

        final_intent = self.current_state["intent"]
        final_slots = self.current_state["slots"].copy()
        self._reset()

        return f"SUCCESS_EXECUTE|{final_intent}|{json.dumps(final_slots)}"

    def handle_follow_up(self, user_input: str) -> str:
        """Called when is_waiting=True. Stores the user answer and re-processes."""
        if not self.current_state["is_waiting"]:
            return None

        entity_name = self.current_state["waiting_for"]
        self.current_state["slots"][entity_name] = user_input.strip()

        # Re-process with same intent so next missing entity (if any) is prompted
        return self.process_prediction(
            [{"intent": self.current_state["intent"]}],
            self.current_state["slots"],
        )

    def execute_direct(self, intent_name: str, slots: dict) -> str:
        """Bypass slot-filling and go straight to execution format."""
        return f"SUCCESS_EXECUTE|{intent_name}|{json.dumps(slots)}"


if __name__ == "__main__":
    sm = StateManager()

    print("User: schedule a meeting")
    r = sm.process_prediction([{"intent": "schedule_meeting"}], {})
    print(f"Jarvis: {r}")

    print("User: with Shivang")
    r = sm.handle_follow_up("with Shivang")
    print(f"Jarvis: {r}")

    print("User: at 5 PM")
    r = sm.handle_follow_up("at 5 PM")
    print(f"Jarvis: {r}")
