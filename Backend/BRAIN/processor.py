# processor.py (refactored)
import json
import os
import datetime
from FUNCTION.SPEAK.speak import JarvisSpeaker

speaker = JarvisSpeaker()

# Try to use rapidfuzz if present for better fuzzy matching
try:
    from rapidfuzz import fuzz, process as rprocess
    RAPIDFUZZ = True
except Exception:
    import difflib
    RAPIDFUZZ = False

# --- Dynamically get the path to commands.json ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMANDS_PATH = os.path.join(BASE_DIR, "DATA", "COMMANDS", "commands.json")

with open(COMMANDS_PATH, "r", encoding="utf-8") as f:
    COMMANDS = json.load(f)

# Precompute all keyword -> command mapping for faster matching
_KEYWORD_TO_COMMAND = {}
for key, data in COMMANDS.items():
    for kw in data.get("keywords", []):
        _KEYWORD_TO_COMMAND[kw.lower()] = key

# fuzzy thresholds (tuneable)
FUZZY_THRESHOLD = 70 if RAPIDFUZZ else 0.6

def find_best_match(user_input: str):
    user_input = (user_input or "").lower().strip()
    if not user_input:
        return None, None

    # 1) direct substring match (fast)
    for key, data in COMMANDS.items():
        for phrase in data.get("keywords", []):
            phrase_l = phrase.lower()
            if phrase_l in user_input:
                return key, data

    # 2) word-token overlap: checks if any keyword words occur in input
    tokens = set(user_input.split())
    for key, data in COMMANDS.items():
        for phrase in data.get("keywords", []):
            if set(phrase.lower().split()).intersection(tokens):
                return key, data

    # 3) fuzzy matching: rapidfuzz (preferred) or difflib fallback
    all_phrases = list(_KEYWORD_TO_COMMAND.keys())
    if RAPIDFUZZ:
        # get best match and its score
        best = rprocess.extractOne(user_input, all_phrases, scorer=fuzz.token_sort_ratio)
        if best and best[1] >= FUZZY_THRESHOLD:
            matched_phrase = best[0]
            command_key = _KEYWORD_TO_COMMAND.get(matched_phrase)
            return command_key, COMMANDS[command_key]
    else:
        best = difflib.get_close_matches(user_input, all_phrases, n=1, cutoff=FUZZY_THRESHOLD)
        if best:
            command_key = _KEYWORD_TO_COMMAND.get(best[0])
            return command_key, COMMANDS[command_key]

    return None, None


def execute_command(command_key, data):
    """
    Decides how to run the action. Keep TTS feedback here, but delegate heavy actions to control.py
    """
    if not command_key or not data:
        speaker.speak("Sorry, I didn't understand that command.")
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
