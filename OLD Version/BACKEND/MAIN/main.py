# main.py
from FUNCTION.LISTEN.listen import listen
from FUNCTION.SPEAK.speak import JarvisSpeaker
from BRAIN.processor import execute_command, find_best_match
import time

def jarvis_local():
    speaker = JarvisSpeaker()
    speaker.speak("Hello Shivang, I am ready to assist you.")

    while True:
        query = listen()
        if not query:
            continue

        if any(x in query.lower() for x in ["exit", "quit", "stop", "bye"]):
            speaker.speak("Goodbye, have a great day.")
            break

        key, data = find_best_match(query)
        response = execute_command(key, data)

        if response:
            print(f"Jarvis: {response}")
            speaker.speak(response)

        time.sleep(0.5)

if __name__ == "__main__":
    jarvis_local()
