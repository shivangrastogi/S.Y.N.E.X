# test_model_large.py
# A comprehensive test suite to evaluate your JARVIS NLU model.

import spacy
import sys
import re
import random

# --- DEFINE YOUR TEST CASES HERE ---
# This list is built to test the 11 intents from your training data.
# Format: ( "Test Phrase with [entity](label)", "expected_intent", {expected_entities} )

TEST_CASES = [
    # == Intent: greet ==
    ("hello", "greet", {}),
    ("नमस्ते", "greet", {}),
    ("hey jarvis", "greet", {}),
    ("what’s up", "greet", {}),
    ("kya hal chal mere dost", "greet", {}),

    # == Intent: goodbye ==
    ("bye", "goodbye", {}),
    ("see you later", "goodbye", {}),
    ("अलविदा", "goodbye", {}),
    ("good night jarvis", "goodbye", {}),
    ("fir milte hai", "goodbye", {}),

    # == Intent: check_time ==
    ("what time is it", "check_time", {}),
    ("samay kya hua hai", "check_time", {}),
    ("what’s the time in [London](location)", "check_time", {"location": "London"}),
    ("[Tokyo](location) mein kya time hai", "check_time", {"location": "Tokyo"}),
    ("[America](location) ka time kya hai", "check_time", {"location": "America"}),
    ("tell me time in [Delhi](location)", "check_time", {"location": "Delhi"}),
    ("[Paris](location) time please", "check_time", {"location": "Paris"}),

    # == Intent: check_weather ==
    ("how's the weather", "check_weather", {}),
    ("aaj ka mausam kaisa hai", "check_weather", {}),
    ("will it rain today", "check_weather", {}),
    ("weather in [Delhi](location)", "check_weather", {"location": "Delhi"}),
    ("what's the temperature in [Pune](location)", "check_weather", {"location": "Pune"}),
    ("aaj [Noida](location) mein mausam kaisa hai", "check_weather", {"location": "Noida"}),
    ("[London](location) ka mausam batao", "check_weather", {"location": "London"}),
    # This was our original bug, it should pass now
    ("[पुणे](location) का मौसम बताओ", "check_weather", {"location": "पुणे"}),

    # == Intent: open_software ==
    ("open [chrome](app_name)", "open_software", {"app_name": "chrome"}),
    ("launch [Visual Studio Code](app_name)", "open_software", {"app_name": "Visual Studio Code"}),
    ("[youtube](app_name) खोलो", "open_software", {"app_name": "youtube"}),
    ("open browser", "open_software", {}),
    ("open my [music player](app_name)", "open_software", {"app_name": "music player"}),
    ("start [Task Manager](app_name)", "open_software", {"app_name": "Task Manager"}),
    ("open [Google Chrome](app_name)", "open_software", {"app_name": "Google Chrome"}),

    # == Intent: search_youtube ==
    ("search youtube for [python tutorials](search_query)", "search_youtube", {"search_query": "python tutorials"}),
    ("youtube par [new songs](search_query) search karo", "search_youtube", {"search_query": "new songs"}),
    ("यूट्यूब पर [कैसे करें](search_query) खोजें", "search_youtube", {"search_query": "कैसे करें"}),
    ("find [kitchen recipes](search_query) on youtube", "search_youtube", {"search_query": "kitchen recipes"}),
    ("play [lofi beats](search_query) on youtube", "search_youtube", {"search_query": "lofi beats"}),

    # == Intent: check_internet_speed ==
    ("run a speed test", "check_internet_speed", {}),
    ("internet speed batao", "check_internet_speed", {}),
    ("how fast is my connection", "check_internet_speed", {}),
    ("स्पीड टेस्ट करो", "check_internet_speed", {}),
    ("run ookla test", "check_internet_speed", {}),

    # == Intent: ask_question ==
    ("what is [AI](query)", "ask_question", {"query": "AI"}),
    ("[भारत](query) की राजधानी क्या है", "ask_question", {"query": "भारत"}),
    ("who is [Shah Rukh Khan](query)", "ask_question", {"query": "Shah Rukh Khan"}),
    ("tell me about [the taj mahal](query)", "ask_question", {"query": "the taj mahal"}),
    # This was a tricky one. Your data has it as 'ask_question'
    ("[दिल्ली](query) का मौसम कैसा है", "ask_question", {"query": "दिल्ली"}),
    ("[AI](query) kya karta hai", "ask_question", {"query": "AI"}),

    # == Intent: chit_chat ==
    ("tell me a joke", "chit_chat", {}),
    ("you are cool", "chit_chat", {}),
    ("क्या चल रहा है", "chit_chat", {}),
    ("make me laugh", "chit_chat", {}),
    ("tum smart ho", "chit_chat", {}),

    # == Intent: add_google_calendar_event ==
    ("schedule a [team sync](title) for [tomorrow](date) at [4pm](start_time)", "add_google_calendar_event",
     {"title": "team sync", "date": "tomorrow", "start_time": "4pm"}),
    ("add [Dentist Appointment](title) on [November 20th](date)", "add_google_calendar_event",
     {"title": "Dentist Appointment", "date": "November 20th"}),
    ("book [Lunch with Mom](title) from [1pm](start_time) to [2pm](end_time) [today](date)",
     "add_google_calendar_event",
     {"title": "Lunch with Mom", "start_time": "1pm", "end_time": "2pm", "date": "today"}),
    ("[कल](date) [शाम 5 बजे](start_time) [मीटिंग](title) सेट करो", "add_google_calendar_event",
     {"date": "कल", "start_time": "शाम 5 बजे", "title": "मीटिंग"}),
    ("[Doctor visit](title) book karo [parso](date) [11am](start_time) ka", "add_google_calendar_event",
     {"title": "Doctor visit", "date": "parso", "start_time": "11am"}),

    # == Intent: play_youtube_song ==
    ("play [Uptown Funk](song_name)", "play_youtube_song", {"song_name": "Uptown Funk"}),
    ("play [Bohemian Rhapsody](song_name) by [Queen](artist)", "play_youtube_song",
     {"song_name": "Bohemian Rhapsody", "artist": "Queen"}),
    ("I want to hear [The Weeknd](artist)", "play_youtube_song", {"artist": "The Weeknd"}),
    ("put on some [classic rock](genre)", "play_youtube_song", {"genre": "classic rock"}),
    ("[Arijit Singh](artist) ke gaane bajao", "play_youtube_song", {"artist": "Arijit Singh"}),
    ("[Tum Hi Ho](song_name) play karo", "play_youtube_song", {"song_name": "Tum Hi Ho"}),
]
# --- END OF TEST CASES ---


# Helper function to clean the markdown [text](label) -> text
ENTITY_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_markdown(markdown_text):
    clean_text = ""
    last_end = 0
    for match in ENTITY_REGEX.finditer(markdown_text):
        clean_text += markdown_text[last_end:match.start()]
        clean_text += match.group(1)  # Just the text, not the label
        last_end = match.end()
    clean_text += markdown_text[last_end:]
    return clean_text


# --- Main Test Runner ---
def run_tests():
    MODEL_PATH = "./models/model-best"
    try:
        nlp = spacy.load(MODEL_PATH)
        print(f"✅ Loaded model from {MODEL_PATH}")
    except IOError:
        print(f"❌ Error: Model not found at {MODEL_PATH}")
        print("Please make sure you have trained your model and it is in the 'models/model-best' folder.")
        sys.exit()

    print(f"\n--- Running {len(TEST_CASES)} Test Cases ---")

    passed = 0
    failed = 0

    # Shuffle tests to run in a random order
    random.shuffle(TEST_CASES)

    for (test_phrase_md, expected_intent, expected_entities) in TEST_CASES:

        # Clean the "[text](label)" markdown into a normal phrase
        test_phrase = parse_markdown(test_phrase_md)

        # Run the model
        doc = nlp(test_phrase)

        # Get model predictions
        pred_intent = max(doc.cats, key=doc.cats.get)
        pred_entities = {ent.label_: ent.text for ent in doc.ents}

        # --- Check results ---
        intent_passed = pred_intent == expected_intent

        # Check if all expected entities were found correctly
        entities_passed = True
        if len(pred_entities) != len(expected_entities):
            entities_passed = False
        else:
            for ent_label, ent_text in expected_entities.items():
                if pred_entities.get(ent_label) != ent_text:
                    entities_passed = False
                    break

        if intent_passed and entities_passed:
            passed += 1
            print(f"✅ PASS: '{test_phrase}'")
        else:
            failed += 1
            print(f"❌ FAIL: '{test_phrase}'")
            if not intent_passed:
                print(f"   -> Intent: Expected '{expected_intent}', Got '{pred_intent}'")
            if not entities_passed:
                print(f"   -> Entities: Expected {expected_entities}, Got {pred_entities}")

    # --- Print Summary ---
    print("\n--- Test Summary ---")
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print(f"TOTAL:  {len(TEST_CASES)}")
    if len(TEST_CASES) > 0:
        accuracy = (passed / len(TEST_CASES)) * 100
        print(f"Accuracy: {accuracy:.2f}%")
    else:
        print("No test cases found.")


if __name__ == "__main__":
    run_tests()