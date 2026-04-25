import time
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.stt import STT
from core.tts import TTS
from core.brain import JarvisBrain
from core.entity_extractor import EntityExtractor
from core.state_manager import StateManager
from core.executor import ActionExecutor

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class JarvisMainEngine:
    def __init__(self):
        print("Initializing A.E.R.I.S v3.1 Semantic Core...")

        self.stt = STT()
        self.tts = TTS()
        self.brain = JarvisBrain()
        self.entity_extractor = EntityExtractor(
            entities_path=os.path.join(_ROOT, "data", "entities.json"),
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
        )
        self.state = StateManager()
        self.executor = ActionExecutor()
        self.is_running = True

        print("A.E.R.I.S is online.")

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _respond(self, text: str):
        """Single point for all Jarvis output — TTS + optional UI hook."""
        self.tts.speak(text)

    def _split_commands(self, command: str) -> list:
        conjunctions = [" and ", " aur ", " then ", " phir ", " also "]
        parts = [command]
        for conj in conjunctions:
            expanded = []
            for p in parts:
                expanded.extend(p.split(conj))
            parts = expanded
        return parts

    def _extract_entities(self, text: str, intent: str) -> dict:
        return self.entity_extractor.extract(text, intent)

    def _handle_result(self, result: str):
        """Parse state-manager result and either execute or speak the prompt."""
        if not result:
            return

        if result.startswith("SUCCESS_EXECUTE|"):
            parts = result.split("|", 2)
            intent = parts[1]
            slots = json.loads(parts[2])
            response = self.executor.execute(intent, slots)
            self._respond(response)
        else:
            # A clarification prompt asking for a missing entity
            self._respond(result)

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        self._respond("AERIS systems online. Ready to help, sir.")

        while self.is_running:
            try:
                command = self.stt.listen()

                if not command:
                    time.sleep(0.3)
                    continue

                print(f"You: {command}")

                # If we are mid-conversation waiting for a missing entity,
                # treat this utterance as the answer to that prompt.
                if self.state.current_state["is_waiting"]:
                    result = self.state.handle_follow_up(command)
                    self._handle_result(result)
                    continue

                # Split multi-commands joined by Hinglish conjunctions
                for sub in self._split_commands(command):
                    sub = sub.strip()
                    if not sub:
                        continue

                    predictions = self.brain.predict_intent(sub)

                    if not predictions:
                        self._respond("Samajh nahi aaya. Please repeat, sir.")
                        continue

                    entities = self._extract_entities(sub, predictions[0]["intent"])
                    result = self.state.process_prediction(predictions, entities)
                    self._handle_result(result)

            except KeyboardInterrupt:
                self._respond("Shutting down. Goodbye, sir!")
                self.is_running = False
            except Exception as e:
                print(f"Engine Error: {e}")
                time.sleep(1)


if __name__ == "__main__":
    engine = JarvisMainEngine()
    engine.run()
