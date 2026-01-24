import re

def detect_intent_from_command(command: str):
    command = command.lower().strip()

    # ---- PROFILE ----
    if re.search(r"(login|sign in|create|connect).*(profile|account)", command):
        return "create_user_profile"

    # ---- CONTACT SYNC ----
    if re.search(r"(refresh|sync|update).*(contact)", command):
        return "refresh_contacts"

    # ---- WHATSAPP ----
    if re.search(r"(send|text|message).*(whatsapp)", command):
        return "send_whatsapp_message"

    return None
