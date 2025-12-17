# BACKEND/AUTOMATION/ActionRouter.py

import webbrowser
import os
import random
import json
import subprocess
import socket
import datetime
import psutil

from AUTOMATION.Modules.BatteryAutomation import get_battery_percentage
from AUTOMATION.Modules.NetworkInfo import get_ip_report
from AUTOMATION.Modules.OnlineStatus import get_online_status_report
from AUTOMATION.Modules.TimeInfo import get_time_report
from CORE.Utils.Logger import log_retrain
from DATA.RESOURCES import responses
from DATA.CONFIG import app_map
from AUTOMATION.Modules.WhatsAppAutomation import send_whatsapp_message
from AUTOMATION.Modules.WhatsAppParser import extract_name_and_message
from AUTOMATION.Modules.UserProfileManager import (
    profile_exists,
    load_profile,
    create_profile
)
from AUTOMATION.Modules.GoogleAuth import google_login
from AUTOMATION.Modules.GoogleContactsSync import fetch_and_save_contacts

# --- Memory File Path (Remains the same) ---
# MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "DATA", "memory.json")
MEMORY_FILE = r'BACKEND/DATA/RESOURCES/memory.json'


def _load_memory():
    # ... (loading memory logic) ...
    try:
        if not os.path.exists(MEMORY_FILE):
            _save_memory({"user_name": None, "memory_facts": []})
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading memory: {e}")
        return {"user_name": None, "memory_facts": []}


def _get_preferred_name():
    profile = load_profile()
    return profile.get("preferred_name") if profile else "Sir"


def _open_youtube_video(speaker, query):
    """
    Constructs a URL to search YouTube for the query and opens the search results
    in the default web browser. The user will see the search page with the video
    at the top, ready to be clicked.
    """
    if not query:
        speaker.speak("I'm sorry, Sir, I need a song or video title to search for.")
        return

    # Use a standard YouTube search URL, optimized for search term.
    # The 'q=' parameter handles the search query.
    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

    # OPTIONAL: To directly play the FIRST video, you'd need a library like
    # youtube-search-python to get the *exact* video URL first.
    # For now, we open the search page which is robust.

    speaker.speak(f"Opening YouTube search for '{query}' in your browser, Sir.")
    webbrowser.open(search_url)


def UI_SIGNAL_UPDATE(status_code, text=None):
    """
    Placeholder: Use this function call throughout actions.py
    to send status updates back to the UI thread.
    """
    # This will be replaced by the Qt signal in the runner file
    pass


def _save_memory(data):
    # ... (saving memory logic) ...
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving memory: {e}")


def _get_local_time():
    return datetime.datetime.now().strftime("%I:%M %p")


# inside actions.py

def _run_speed_test(speaker):
    try:
        # Ensure the file is at: functional/CHECK_SPEED/speed_test.py
        from .Modules.NetSpeed import check_download_speed

        speaker.speak("Running a network speed analysis, Sir. Please wait.")

        speed_mbps = check_download_speed()

        if speed_mbps is not None:
            return f"The download speed is approximately {speed_mbps:.2f} Megabits per second, Sir."
        else:
            return "Apologies, Sir. I could not connect to the speed test server."

    except ImportError:
        print("ERROR: Could not find speed_test.py in FUNCTION/CHECK_SPEED/")
        return "Sir, the speed test module appears to be missing."
    except Exception as e:
        print(f"INTERNET_SPEED_FAIL | Error: {e}")
        return "Apologies, Sir. I encountered an internal error."


# --------------------------------------------------------
# --- PROCESS CONTROL HELPER (psutil) ---
# --------------------------------------------------------

def _map_to_process_name(item_name):
    """Maps common app names to their exact Windows executable name."""
    name_lower = item_name.lower().strip()

    PROCESS_MAPPING = {
        "edge": "msedge.exe",
        "google chrome": "chrome.exe",
        "chrome": "chrome.exe",
        "visual studio code": "code.exe",
        "vs code": "code.exe",
        "notepad": "notepad.exe",
        "file explorer": "explorer.exe",
        "explorer": "explorer.exe",
        "calculator": "calc.exe",
        "terminal": "cmd.exe",
        "task manager": "taskmgr.exe",
        "spotify": "spotify.exe",
        "discord": "discord.exe",
        "telegram": "telegram.exe",
        "whatsapp": "whatsapp.exe",
        "postman": "postman.exe",
    }

    if name_lower in PROCESS_MAPPING:
        return PROCESS_MAPPING[name_lower]

    return name_lower + ".exe" if not name_lower.endswith('.exe') else name_lower


def _kill_process_psutil(process_name, speaker):
    """
    Finds and terminates a process using the psutil library.
    """
    target_name = process_name.lower()
    killed_count = 0

    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == target_name:
            try:
                proc.terminate()  # Request process to terminate gracefully
                killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                log_retrain(f"ACCESS_DENIED | Failed to kill {target_name}")
                pass

    if killed_count > 0:
        # Success message spoke by the function
        speaker.speak(f"Successfully closed {killed_count} instances of {process_name.replace('.exe', '')}, Sir.")
        return True
    else:
        # Failure message spoke by the function
        speaker.speak(f"Apologies, Sir. I found no running process named {process_name.replace('.exe', '')}.")
        return False


# --------------------------------------------------------
# --- DYNAMIC OPEN HELPER ---
# --------------------------------------------------------

def _handle_dynamic_open(speaker, item_name):
    """
    Tries to open an item using the 4-step fallback logic.
    """
    item_lower = item_name.lower().strip()

    # --- Try 1: Check Local App Map (Fastest) ---
    if item_lower in app_map.LOCAL_APPS:
        speaker.speak(f"{random.choice(responses.OPEN_RESPONSES)} {item_name}, Sir.")
        os.system(app_map.LOCAL_APPS[item_lower])
        return

    # --- Try 2: Check Website Map (Fast) ---
    if item_lower in app_map.WEBSITES:
        speaker.speak(f"{random.choice(responses.OPEN_RESPONSES)} {item_name}, Sir.")
        webbrowser.open(app_map.WEBSITES[item_lower])
        return

    # --- Try 3: Dynamic Local App (subprocess.Popen) ---
    try:
        speaker.speak(f"As you wish, Sir. Attempting to launch {item_name}.")
        subprocess.Popen(item_lower, shell=True)
        return
    except Exception as e:
        print(f"[Dynamic Open] Failed to launch '{item_lower}' as a process. Trying website...")

    # --- Try 4: Dynamic Website (Fallback) ---
    try:
        url = f"https://www.{item_lower.replace(' ', '')}.com"
        webbrowser.open(url)
        speaker.speak(f"I could not find a local app, Sir. Opening {url} instead.")
        return
    except Exception as e:
        print(f"[Dynamic Open] Failed to open '{url}'.")

    # --- All Fallbacks Failed ---
    log_msg = f"APP_MAP_MISSING | Could not find any action for '{item_name}'"
    print(f"({log_msg})")
    log_retrain(log_msg)
    speaker.speak(f"Apologies, Sir. I don't have a shortcut for '{item_name}' and I was unable to find it.")


# --------------------------------------------------------
# --- MAIN ACTION ROUTER ---
# --------------------------------------------------------

def handle_action(speaker, command, intent, entities):
    """
    Selects and executes the correct action based on the NLU intent.
    """
    print(f"[Action] Handling: {intent}")

    # --- GREET / GOODBYE / MEMORY SKILLS (Remain the same) ---
    if intent == "greet":
        speaker.speak(random.choice(responses.GREET_RESPONSES))
    elif intent == "goodbye":
        speaker.speak(random.choice(responses.GOODBYE_RESPONSES))
        return False

    elif intent == "set_user_name":
        name = entities.get("USER_NAME")
        if name:
            memory = _load_memory()
            memory["user_name"] = name
            _save_memory(memory)
            speaker.speak(f"Acknowledged. I will remember your name is {name}, Sir.")
        else:
            speaker.speak("I'm sorry, Sir, I didn't catch the name.")
    elif intent == "manage_user_name":
        new_name = entities.get("USER_NAME")
        memory = _load_memory()
        if new_name:
            # --- LOGIC TO CHANGE NAME ---
            memory["user_name"] = new_name
            _save_memory(memory)
            speaker.speak(f"Name successfully updated. I will now call you {new_name}, Sir.")
        else:
            if memory.get("user_name"):
                memory["user_name"] = None
                _save_memory(memory)
                speaker.speak("Acknowledged. I have removed your name from my memory, Sir.")
            else:
                speaker.speak("Sir, I currently do not have a user name stored to forget.")

    elif intent == "get_user_name":
        memory = _load_memory()
        name = memory.get("user_name")
        if name:
            speaker.speak(f"Your name is {name}, Sir.")
        else:
            speaker.speak("You have not told me your name yet, Sir.")

    elif intent == "memory_store":
        fact = entities.get("memory_fact")
        if fact:
            memory = _load_memory()
            if fact not in memory["memory_facts"]:
                memory["memory_facts"].append(fact)
            _save_memory(memory)
            speaker.speak(f"Acknowledged, Sir. I have stored that fact.")
        else:
            speaker.speak("I'm sorry, Sir, what was it you wanted me to remember?")

    elif intent == "memory_recall":
        memory = _load_memory()
        facts = memory.get("memory_facts", [])
        if not facts:
            speaker.speak("I do not have any specific facts stored for you, Sir.")
        else:
            speaker.speak("Here is what I have on file, Sir:")
            for fact in facts:
                speaker.speak(fact)
    elif intent == "memory_forget":
        fact_to_forget = entities.get("memory_fact")
        memory = _load_memory()
        if fact_to_forget:
            original_count = len(memory["memory_facts"])
            memory["memory_facts"] = [
                fact for fact in memory["memory_facts"]
                if fact.lower() != fact_to_forget.lower()
            ]
            if len(memory["memory_facts"]) < original_count:
                _save_memory(memory)
                speaker.speak(f"I have removed the fact about '{fact_to_forget}', Sir.")
            else:
                speaker.speak(f"Apologies, Sir. I couldn't find the fact '{fact_to_forget}' in my memory.")
        else:
            memory["memory_facts"] = []
            _save_memory(memory)
            speaker.speak("As you wish, Sir. I have cleared all stored facts from local memory.")
    elif intent == "check_time":
        time_str = _get_local_time()
        response = f"The current time is {time_str}, Sir."
        speaker.speak(response)
        return response

    elif intent == "check_ip":
        report = get_ip_report()
        speaker.speak(report)
        return report

    elif intent == "check_online_status":
        report = get_online_status_report()
        speaker.speak(report)
        return report

    elif intent == "send_whatsapp_message":
        if not profile_exists():
            speaker.speak(
                "You are not logged in yet. Please say create my profile to continue."
            )
            return True
        name, message = extract_name_and_message(command)
        if not name or not message:
            speaker.speak(
                "Please tell me the contact name and the message."
            )
            return True
        response = send_whatsapp_message(name, message, speaker)
        speaker.speak(response)
        return True

    elif intent == "create_user_profile":

        if profile_exists():
            speaker.speak("Your profile is already connected.")
            return True

        speaker.speak("Please login with your Google account.")

        google_data = google_login()

        speaker.speak(
            f"What should I call you? You can say {google_data['full_name']} or any other name."
        )

        preferred_name = entities.get("USER_NAME") or google_data["full_name"]

        create_profile(google_data, preferred_name)

        speaker.speak("Fetching your contacts now.")
        fetch_and_save_contacts()

        speaker.speak(f"Your profile setup is complete, {preferred_name}.")
        return True

    elif intent == "refresh_contacts":

        if not profile_exists():
            speaker.speak("Please create your profile first.")
            return True

        speaker.speak("Refreshing your Google contacts.")
        contacts = fetch_and_save_contacts()

        speaker.speak(f"{len(contacts)} contacts updated successfully.")
        return True


    elif intent == "check_time":
        report = get_time_report()
        speaker.speak(report)
        return report  # 🔴 MUST return string

    elif intent == "search_youtube":
        query = entities.get("search_query", "")
        if not query:
            speaker.speak(random.choice(responses.ASK_FOR_SONG_RESPONSES))
        else:
            # Revert to the standard search behavior (opens search results)
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            speaker.speak(f"{random.choice(responses.YT_SEARCH_RESPONSES)} for '{query}', Sir.")
            webbrowser.open(search_url)

    elif intent == "play_youtube_song":
        # Consolidate entities that suggest a specific media item
        query = entities.get("song_name") or entities.get("artist") or entities.get("genre")

        if query:
            # NEW LOGIC: Use the helper to search and open in browser
            _open_youtube_video(speaker, query)
        else:
            speaker.speak(random.choice(responses.ASK_FOR_SONG_RESPONSES))

    elif intent == "check_internet_speed":
        response = _run_speed_test(speaker)
        speaker.speak(response)
        return response

    elif intent in ["check_battery_percentage", "battery_plug_check", "battery_alert"]:
        response = get_battery_percentage()
        speaker.speak(response)
        return response

    elif intent == "close_item":
        item_to_close = entities.get("target_item", "").strip()

        # --- GUESSING FALLBACK (If NLU missed the entity) ---
        if not item_to_close:
            print("[Action] NLU missed entity. Applying Guessing Fallback...")
            words = command.lower().split()
            if len(words) > 1:
                item_name = " ".join(words[1:])
                item_to_close = item_name.replace("browser", "").replace("app", "").replace("tab", "").strip()
        # --- END GUESSING FALLBACK ---

        if item_to_close in ["current window", "saare tabs", "all tabs", "browser"]:
            # Close all browser instances using psutil
            _kill_process_psutil("chrome.exe", speaker)
            _kill_process_psutil("msedge.exe", speaker)
            speaker.speak("Closing all open browser windows, Sir.")

        elif item_to_close:
            # 1. Get the correct executable name (e.g., 'edge' -> 'msedge.exe')
            process_name = _map_to_process_name(item_to_close)

            # 2. Execute the kill command via psutil
            _kill_process_psutil(process_name, speaker)

        else:
            speaker.speak("I'm sorry, Sir. What application or tab did you want to close?")


    # --- DYNAMIC OPEN ITEM ---
    elif intent in ["open_target", "open_item"]:
        item_to_open = entities.get("target_item", "").strip()

        # Fallback logic if NLU misses the entity
        if not item_to_open:
            print("[Action] NLU found no entity. Trying to guess from command...")
            words = command.lower().split()
            if len(words) > 1:
                item_name = " ".join(words[1:])
                item_to_open = item_name.replace("website", "").replace("app", "").strip()

        if not item_to_open:
            log_msg = f"NLU_ENTITY_FAIL | Command: \"{command}\" | Intent: {intent}"
            print(f"({log_msg})")
            log_retrain(log_msg)
            speaker.speak("Sorry, Sir. What was it you wanted me to open?")
            return True

        _handle_dynamic_open(speaker, item_to_open)

    # --- PLACEHOLDERS / FALLBACK ---
    elif intent == "search_youtube":
        query = entities.get("search_query", "")
        if not query:
            speaker.speak(random.choice(responses.ASK_FOR_SONG_RESPONSES))
        else:
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            speaker.speak(f"{random.choice(responses.YT_SEARCH_RESPONSES)} for '{query}', Sir.")
            webbrowser.open(search_url)

    elif intent == "play_youtube_song":
        speaker.speak(responses.get_response(intent))

    # --- Default for Out of Scope or UNHANDLED INTENT ---
    else:
        speaker.speak(responses.get_response(intent))

    return True
