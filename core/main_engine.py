import time
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.stt import STT
from core.tts import TTS
from core.neural_engine import NeuralEngine
from core.state_manager import StateManager
from core.executor import ActionExecutor

class JarvisMainEngine:
    def __init__(self):
        print("Initializing A.E.R.I.S v3.0 Core...")
        
        # Initialize all subsystems
        self.stt = STT()
        self.tts = TTS()
        self.brain = NeuralEngine()
        self.state_manager = StateManager()
        self.executor = ActionExecutor()
        
        self.is_running = True
        print("Jarvis is online and ready.")

    def run(self):
        self.tts.speak("AERIS systems are online. How can I help you, sir?")
        
        while self.is_running:
            try:
                # 1. Listen for voice
                command = self.stt.listen()
                
                if not command:
                    time.sleep(0.5) # Prevents CPU spike if loop is too fast
                    continue

                    
                print(f"You said: {command}")

                # 2. Check if we are in a follow-up state
                if self.state_manager.current_state["is_waiting"]:
                    response = self.state_manager.handle_follow_up(command)
                else:
                    # 3. Predict Intent
                    predictions = self.brain.predict_intent(command)
                    
                    if predictions:
                        # 4. Smart Entity Extraction (Dynamic)
                        extracted = {}
                        command_lower = command.lower()
                        
                        # Logic: Look for common apps OR the word after "open/close/kholo/band"
                        words = command_lower.split()
                        trigger_words = ["open", "close", "start", "launch", "kholo", "band", "chalu"]
                        
                        for i, word in enumerate(words):
                            if word in trigger_words and i + 1 < len(words):
                                # Take the very next word as the app name
                                extracted["app_name"] = words[i+1]
                                break
                        
                        # Fallback for known apps if the above logic missed it
                        if "app_name" not in extracted:
                            for app in ["chrome", "notepad", "calculator", "visual studio code", "brave", "edge"]:
                                if app in command_lower:
                                    extracted["app_name"] = app
                        
                        response = self.state_manager.process_prediction(predictions, extracted)

                    else:
                        response = "Sorry, I didn't understand that command."

                # 5. Handle Execution Result
                if response.startswith("SUCCESS_EXECUTE"):
                    # Split the response to get intent and slots
                    _, intent, slots_json = response.split("|")
                    import json
                    slots = json.loads(slots_json)
                    
                    final_action_result = self.executor.execute(intent, slots)
                    self.tts.speak(final_action_result)
                else:
                    # This is likely a follow-up question or an error
                    self.tts.speak(response)


            except KeyboardInterrupt:
                print("Shutting down Jarvis...")
                self.tts.speak("Goodbye, sir.")
                self.is_running = False
            except Exception as e:
                print(f"Engine Error: {str(e)}")
                time.sleep(1)

if __name__ == "__main__":
    engine = JarvisMainEngine()
    engine.run()
