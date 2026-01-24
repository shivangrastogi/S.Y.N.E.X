from flask import Flask, request, jsonify
from flask_cors import CORS
from BRAIN.processor import execute_command, find_best_match
from DATA.FIREBASE.AUTH.firebase_auth import login_user, register_user
from FUNCTION.LISTEN.listen import listen
from FUNCTION.SPEAK.speak import JarvisSpeaker
import threading
import time

app = Flask(__name__)
CORS(app)

# Globals
speaker = JarvisSpeaker()
jarvis_running = False
jarvis_logs = []


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = register_user(email, password)
    if user:
        return jsonify({"success": True, "message": "Account created successfully"})
    return jsonify({"success": False, "message": "Error creating account"})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = login_user(email, password)
    if user:
        return jsonify({"success": True, "message": "Login successful"})
    return jsonify({"success": False, "message": "Login failed"})


@app.route("/start-jarvis", methods=["POST"])
def start_jarvis():
    global jarvis_running
    if jarvis_running:
        return jsonify({"message": "Jarvis is already running"})
    jarvis_running = True
    threading.Thread(target=jarvis_main_loop, daemon=True).start()
    return jsonify({"message": "Jarvis started"})


@app.route("/get-logs", methods=["GET"])
def get_logs():
    """Return chat logs to frontend"""
    return jsonify({"logs": jarvis_logs})


def jarvis_main_loop():
    global jarvis_running, jarvis_logs
    try:
        speaker.speak("Hello, Mr. Shivang. Jarvis is now online.")
        jarvis_logs.append({"sender": "Jarvis", "text": "Hello, Mr. Shivang. Jarvis is now online."})

        while jarvis_running:
            query = listen()
            if not query:
                continue

            print(f"User said: {query}")
            jarvis_logs.append({"sender": "User", "text": query})

            if any(x in query.lower() for x in ["exit", "quit", "stop", "bye"]):
                msg = "Goodbye, Mr. Shivang. Have a great day."
                speaker.speak(msg)
                jarvis_logs.append({"sender": "Jarvis", "text": msg})
                jarvis_running = False
                break

            key, data = find_best_match(query)
            response = execute_command(key, data)
            if response:
                jarvis_logs.append({"sender": "Jarvis", "text": response})

    except Exception as e:
        print(f"[ERROR] {e}")
        jarvis_logs.append({"sender": "Jarvis", "text": "Sorry, something went wrong."})
        time.sleep(1)


if __name__ == "__main__":
    print("🔥 Flask server running at: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
