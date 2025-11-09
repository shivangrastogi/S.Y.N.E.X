# processor.py (refactored with NLU)
import json
import os
import datetime
from FUNCTION.SPEAK.speak import JarvisSpeaker
from transformers import pipeline  # <-- NEW IMPORT

speaker = JarvisSpeaker()

# --- Initialize the NLU (Zero-Shot) Classifier ---
# This loads a model that is fast and good at this task.
# It will download the model on the first run.
print("Loading NLU intent classifier...")
classifier = pipeline("zero-shot-classification",
                      model="facebook/bart-large-mnli")
print("✅ NLU classifier loaded.")

# --- Dynamically get the path to commands.json ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMANDS_PATH = os.path.join(BASE_DIR, "DATA", "COMMANDS", "commands.json")

with open(COMMANDS_PATH, "r", encoding="utf-8") as f:
    COMMANDS = json.load(f)

# --- Precompute all labels and mappings for the NLU model ---
# We will use your existing keywords as the "intents" (labels)
_LABEL_TO_COMMAND_KEY = {}
_CANDIDATE_LABELS = []

for key, data in COMMANDS.items():
    for kw in data.get("keywords", []):
        label = kw.lower()
        _LABEL_TO_COMMAND_KEY[label] = key
        _CANDIDATE_LABELS.append(label)

# NLU confidence threshold (tuneable)
NLU_THRESHOLD = 0.70  # Only accept intents with 70% or higher confidence


def find_best_match(user_input: str):
    user_input = (user_input or "").lower().strip()
    if not user_input:
        return None, None

    # === 1) Fast Path: Direct Substring Match ===
    # (Kept from your old code, as it's very fast and reliable for simple commands)
    for key, data in COMMANDS.items():
        for phrase in data.get("keywords", []):
            phrase_l = phrase.lower()
            if phrase_l in user_input:
                print(f"[NLU] Matched via Fast Path: {phrase_l}")
                return key, data

    # === 2) NLU Path: Zero-Shot Intent Recognition ===
    # (This replaces your fuzzy matching logic)
    print(f"[NLU] Using Zero-Shot for: '{user_input}'")
    try:
        # Get the model's prediction
        result = classifier(user_input, _CANDIDATE_LABELS)

        best_label = result['labels'][0]
        best_score = result['scores'][0]

        print(f"[NLU] Best match: '{best_label}' (Score: {best_score:.2f})")

        # Only proceed if the confidence is above our threshold
        if best_score >= NLU_THRESHOLD:
            # Find which command this label belongs to
            command_key = _LABEL_TO_COMMAND_KEY.get(best_label)
            if command_key:
                return command_key, COMMANDS[command_key]

    except Exception as e:
        print(f"Error during NLU classification: {e}")
        # Fallback or error handling
        pass

    # === 3) Fallback ===
    # If no fast match and NLU score is too low
    return None, None


def execute_command(command_key, data):
    """
    Decides how to run the action. (No changes needed here)
    """
    if not command_key or not data:
        speaker.speak("Sorry, I didn't quite understand that.")
        return

    response = data.get("response", "Done.")
    action = data.get("action")  # e.g. "open_chrome" or "tell_time"

    # If action is a special 'internal' type
    if action == "tell_time":
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        response = f"{response} {current_time}"
        speaker.speak(response)
        return

    # For system actions, delegate to control module
    try:
        from FUNCTION.SYSTEM.control import execute_system_command
    except Exception:
        execute_system_command = None

    if action and execute_system_command:
        # Pass action to system controller which returns a friendly response
        act_response = execute_system_command(action, None)
        speaker.speak(act_response or response)
        return

    # Default: speak the response
    speaker.speak(response)