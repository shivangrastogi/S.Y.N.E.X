# jarvis.py
# VERSION 3.4: Added "Learning Loop" Failure Logging

import spacy
import sys
import os
import google.generativeai as genai
import webbrowser  # For opening websites
import random  # For picking random responses
import responses  # Our new personality file
import app_map  # Our new action file
from datetime import datetime  # <-- NEW import for logging timestamp

# --- API KEY CONFIGURATION ---
API_KEY = os.environ.get("GOOGLE_API_KEY")

if not API_KEY:
    # A temporary fix for testing if the env variable isn't set
    # PASTE YOUR NEW, SECRET KEY HERE (and don't share it!)
    # API_KEY = "AIza..."

    if not API_KEY:
        print("❌ Error: GOOGLE_API_KEY environment variable not set.")
        sys.exit()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')

# --- BRAIN 1: Your Custom NLU Model ---
MODEL_PATH = "./models/model-best"
try:
    nlp = spacy.load(MODEL_PATH)
    print("✅ JARVIS Brain 1 (NLU) loaded.")
except IOError:
    print(f"❌ Error: Model not found at {MODEL_PATH}")
    print("Have you run 'python train.py' successfully?")
    sys.exit()


# --- BRAIN 2: The "Talker" / Generative AI ---
def get_generative_answer(query):
    print(f"[Brain 2: Sending to Google AI...]")
    try:
        prompt = f"You are JARVIS, a helpful personal assistant. Be friendly, professional, and concise. Always address the user as 'Sir'. Answer the user's following request: '{query}'"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Brain 2 Error: {e}")
        return "Sorry, Sir. I'm having trouble connecting to my creative circuits right now."


# --- NEW: Logging Function ---
def log_failure(command, intent, confidence):
    """
    Appends a failed command to the log file for later review.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{timestamp} | Command: \"{command}\" | Guessed: {intent} ({confidence:.2f})\n"

    try:
        with open("failed_commands.log", "a", encoding="utf-8") as f:
            f.write(log_message)
    except Exception as e:
        print(f"Error writing to log: {e}")


# --- Action Functions (The 'Doer') ---
def handle_action(intent, entities):
    print(f"[Brain 1: Detected Intent='{intent}']")
    for label, text in entities.items():
        print(f"         > Entity='{label}': {text}")

    if intent == "greet":
        print(f"JARVIS: {random.choice(responses.GREET_RESPONSES)}")

    elif intent == "goodbye":
        print(f"JARVIS: {random.choice(responses.GOODBYE_RESPONSES)}")
        return False  # Signal to exit the loop

    elif intent == "open_software":
        app_name = entities.get("app_name", "").lower()
        if not app_name:
            print("JARVIS: Sorry, Sir. What was it you wanted me to open?")
            return True

        if app_name in app_map.LOCAL_APPS:
            print(f"JARVIS: {responses.get_response(intent)}")
            os.system(app_map.LOCAL_APPS[app_name])

        elif app_name in app_map.WEBSITES:
            print(f"JARVIS: {responses.get_response(intent)}")
            webbrowser.open(app_map.WEBSITES[app_name])

        else:
            print(f"JARVIS: Apologies, Sir. I don't have a shortcut for '{app_name}'.")

    elif intent == "search_youtube":
        query = entities.get("search_query", "")
        if not query:
            print(f"JARVIS: {random.choice(responses.ASK_FOR_SONG_RESPONSES)}")
        else:
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            print(f"JARVIS: {responses.get_response(intent)}")
            webbrowser.open(search_url)

    # --- Other Actions (Not fully built yet) ---
    else:
        print(f"JARVIS: {responses.get_response(intent)}")

    return True  # Signal to continue the loop


# --- The Main "Router" Loop ---
def main():
    print(f"JARVIS: {random.choice(responses.ONLINE_RESPONSES)}")
    CONFIDENCE_THRESHOLD = 0.55

    while True:
        try:
            command = input("\nYou: ")
        except KeyboardInterrupt:
            print(f"\nJARVIS: {random.choice(responses.GOODBYE_RESPONSES)}")
            break

        doc = nlp(command)
        top_intent = max(doc.cats, key=doc.cats.get)
        confidence = doc.cats[top_intent]
        entities = {ent.label_: ent.text for ent in doc.ents}

        # --- The "Two-Brain" Decision ---

        # 1. SUCCESSFUL TASK: Confident & not chat
        if confidence > CONFIDENCE_THRESHOLD and top_intent not in ["ask_question", "chit_chat"]:
            if not handle_action(top_intent, entities):
                break

                # 2. CHAT OR FAILURE
        else:
            # --- THIS IS THE NEW LOGIC ---
            # If it's NOT supposed to be chat, but confidence was low,
            # it's a failure. Log it for review.
            if top_intent not in ["ask_question", "chit_chat"]:
                print("JARVIS: (I'm not sure, Sir. Logging this for review.)")
                log_failure(command, top_intent, confidence)
            # --- END OF NEW LOGIC ---

            # Pass to Brain 2 (The Google AI) for a smart answer
            answer = get_generative_answer(command)
            print(f"JARVIS: {answer}")


if __name__ == "__main__":
    main()