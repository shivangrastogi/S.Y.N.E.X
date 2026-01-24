import os
from datetime import datetime

USER_DATA = os.path.join(os.getenv("APPDATA"), "Jarvis")
os.makedirs(USER_DATA, exist_ok=True)

RESPONSES_FILE = os.path.join(USER_DATA, "Responses.data")
STATUS_FILE = os.path.join(USER_DATA, "Status.data")
MIC_FILE = os.path.join(USER_DATA, "Mic.data")

def append_response(user_msg=None, bot_msg=None):
    with open(RESPONSES_FILE, "a", encoding="utf-8") as f:
        if user_msg:
            f.write(f"[USER] {user_msg}\n")
        if bot_msg:
            f.write(f"[JARVIS]  {bot_msg}\n")


def clear_chat_log():
    with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("=== Session started at %H:%M:%S ===\n"))
