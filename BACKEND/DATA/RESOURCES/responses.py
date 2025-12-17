# responses.py
# This file contains all of JARVIS's scripted "personality" responses.

import random

GREET_RESPONSES = [
    "Rise and shine, sir! Another day to conquer.",
    "Good morning, sir! Champion, ready to tackle the day?",
    "Greetings, sir! Early bird, the world awaits your brilliance.",
    "Hello, world, sir! Let’s make today extraordinary.",
    "Wake up, sir! Superhero, your day of greatness has arrived.",
    "Good afternoon, sir! The sun smiles upon your journey.",
    "Greetings, sir! The afternoon awaits your continued brilliance.",
    "Hello, sir! Afternoon sunshine, ready for your radiance.",
    "Good evening, sir! The day bids adieu to your triumphs.",
    "Greetings, sir! Embrace the serenity of the evening glow.",
    "Hello, sir! Evening tranquility, ready for your brilliance.",
    "Hey there, sir!",
    "Greetings, sir!",
    "Hello again, sir!",
    "Hi, sir!",
    "Good day, sir!",
    "Salutations, sir!",
    "hello sir! jarvis is here",
    "greetings sir! jarvis reporting in",
    "hello there! jarvis is at your service",
    "good day sir! jarvis is present",
    "salutations sir! jarvis reporting for duty",
    "hi there! jarvis is here to assist",
    "hello sir! jarvis is ready and waiting",
    "greetings sir! jarvis is on standby",
    "hello there! jarvis is at your command",
    "good day sir! jarvis is online",
]

GOODBYE_RESPONSES = [
    "Good night, sir! The stars await your dreams.",
    "Greetings, sir! Embrace the tranquility of the night.",
    "A peaceful good night, sir! Ready for a night of restful triumphs?",
    "Goodbye, sir. Take care and feel free to call me anytime.",
    "Farewell, sir. Remember, you can reach out to me whenever you need assistance.",
    "Goodbye, sir. Call me if you need anything. Until next time!",
    "Goodbye, sir. It's always a pleasure assisting you. Take care.",
    "okay sir, farewell",
    "okay sir, goodbye",
    "okay sir, see you later",
    "understood sir, farewell",
    "understood sir, bye",
    "understood sir, take care",
    "affirmative sir, goodbye",
]

ACKNOWLEDGE_RESPONSES = [
    "Engaged.",
    "Affirmative.",
    "Proceeding.",
    "Confirmed.",
    "Understood.",
    "Executing.",
    "Acknowledged.",
    "Accepted.",
    "Approved.",
    "playing...",
    "as you wish",
    "got it",
    "on it",
    "with pleasure",
    "starting now",
    "your command",
    "no problem",
    "done boss",
    "right away",
    "yes boss",
]

OPEN_RESPONSES = [
    "opening...",
    "just a second opening",
    "ok i am gonna open",
    "as your wish opening",
    "yes sir opening",
    "starting",
    "here we go opening",
    "Task accomplished, sir.",
    "Execution successful, results on your screen.",
    "Operation completed, sir. Well done!",
    "Successfully executed, sir. Congratulations!",
]

CLOSE_RESPONSES = [
    "closing",
    "close",
    "just a second sir",
    "got it sir"
]

PLAY_SONG_RESPONSES = [
    "playing..",
    "yes sir",
    "playing now",
    "As you wish, sir. Playing your favorite music on YouTube now.",
    "I'm queuing up some great tunes for you on YouTube.",
    "Let the music play on YouTube.",
    "Your command is my pleasure, sir. Initiating music playback on YouTube.",
]

STOP_MUSIC_RESPONSES = [
    "pausing",
    "stoping",
    "as your wish"
]

ASK_FOR_SONG_RESPONSES = [
    "Which song do you want to play?",
    "Wow, but could you please tell me the name of the song?",
    "Sure, sir. What is the name of the song?",
    "Can you let me know the title of the song you'd like to play?",
    "I'd be happy to play a song for you. What's the name of it?",
]

SEARCHING_RESPONSES = [
    "Sir, now initiating the search for your inquiry.",
    "I'm currently searching for information based on your query.",
    "Let me find the relevant details for your inquiry.",
    "Sir, this is the search result for your question or query.",
    "Here is the information based on your question or inquiry."
]

YT_SEARCH_RESPONSES = [
    "Sir, searching your query on YouTube now for relevant content.",
    "I'll initiate a YouTube search based on your query.",
    "Let me find your query on YouTube for you.",
    "Sir, I'm searching your inquiry on YouTube for related videos.",
]

# --- System Status Responses ---

ONLINE_RESPONSES = [
    "Sir, I am online and ready",
    "Sir, I am online",
    "I am online, sir",
    "Sir, my status is online",
    "I am online, sir, happy to assist you",
    "Online and ready, sir",
]

OFFLINE_RESPONSES = [
    "Sir, I am offline. Please connect to the WiFi or internet",
    "Sir, I am currently offline. Please check the internet connection",
    "I am offline, sir. Kindly connect me to the internet",
    "I apologize, but Jarvis is currently offline, taking a well-deserved rest. I'm Friday, your limited-function offline assistant.",
]

BATTERY_LOW_RESPONSES = [
    "It appears your device is running low on battery. Would you like assistance in finding a charging solution?",
    "Sir, I've noticed a decrease in power levels. Shall I initiate a charging protocol for your device?",
    "I recommend connecting your device to a power source to ensure uninterrupted functionality.",
    "Sir, the energy levels are depleting. May I suggest plugging in your device for a power boost?",
]

BATTERY_CRITICAL_RESPONSES = [
    "Sir, this is your final warning. The battery is critically low. Shall I assist you in finding a charging solution?",
    "Urgent message: your device is running on very low battery. Would you like guidance on charging options?",
    "Your device is on its last bit of power. May I suggest connecting it to a charger immediately?",
    "Sir, immediate action is required. The battery is dangerously low.",
]

BATTERY_FULL_RESPONSES = [
    "Sir, the battery is at 100 percent capacity. It seems fully charged. Would you like to unplug it?",
    "Hello, sir. Battery status: 100 percent. It appears fully charged. Shall I recommend unplugging it?",
    "Battery power is at its peak, 100 percent. Would you prefer to unplug your device now?",
]

PLUGGED_IN_RESPONSES = [
    "Sir, plugging successful. Your device is now charging efficiently.",
    "The device is now plugged in, and the charging process has started.",
    "Plugging accomplished. Your device is currently charging.",
]

PLUGGED_OUT_RESPONSES = [
    "Your device has been unplugged. You are now running on battery power.",
    "The connection has been removed. You are currently operating on battery power.",
    "Sir, the device has been unplugged. You are now relying on your battery for power.",
]


# --- This function will be used by jarvis.py ---
def get_response(intent_name):
    """
    Returns a random, scripted response for a given intent.
    """
    response_map = {
        "greet": GREET_RESPONSES,
        "goodbye": GOODBYE_RESPONSES,
        "open_software": OPEN_RESPONSES,
        "close_software": CLOSE_RESPONSES,
        "play_youtube_song": PLAY_SONG_RESPONSES,
        "stop_music": STOP_MUSIC_RESPONSES,
        "resume_music": ACKNOWLEDGE_RESPONSES,
        "check_internet_speed": ACKNOWLEDGE_RESPONSES,
        "add_google_calendar_event": ACKNOWLEDGE_RESPONSES,
        "search_youtube": YT_SEARCH_RESPONSES,
    }

    responses_list = response_map.get(intent_name)

    if responses_list:
        return random.choice(responses_list)
    else:
        # Fallback for intents we haven't mapped yet
        return random.choice(ACKNOWLEDGE_RESPONSES)