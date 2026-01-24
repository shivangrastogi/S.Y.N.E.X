# --- BACKEND/DATA/CONFIG/command_manifest.py (NEW FILE) ---

COMMAND_MANIFEST = {
    # --- UTILITIES ---
    "check_time": {
        "name": "Check Time",
        "description": "Tells you the current local time.",
        "example": "What time is it in Tokyo?"
    },
    "get_local_ip": {
        "name": "Check Local IP",
        "description": "Reports the local network IP address of your machine.",
        "example": "What is my IP address?"
    },
    "check_internet_speed": {
        "name": "Run Speed Test",
        "description": "Measures your current download bandwidth.",
        "example": "Check internet speed now."
    },

    # --- AUTOMATION/ACTIONS ---
    "open_item": {
        "name": "Launch App/Website",
        "description": "Opens software or navigates to a known website.",
        "example": "Open Spotify / Launch VS Code / Go to GitHub."
    },
    "close_item": {
        "name": "Close App/Window",
        "description": "Closes a running application or browser session.",
        "example": "Close Chrome / Terminate Task Manager."
    },
    "set_reminder": {
        "name": "Set Reminder/Alarm",
        "description": "Schedules a notification for a specific time or event.",
        "example": "Remind me to call John tomorrow at 3 PM."
    },

    # --- MEMORY ---
    "set_user_name": {
        "name": "Set My Name",
        "description": "Stores your name for personalized responses.",
        "example": "Remember my name is Tony."
    },
    "manage_user_name": {
        "name": "Forget/Change Name",
        "description": "Removes or changes your stored user name.",
        "example": "Forget my name / Change my name to Master."
    },
    "memory_store": {
        "name": "Store Fact",
        "description": "Stores a general fact in memory (e.g., 'My dog is Max').",
        "example": "Store that my favorite food is pizza."
    }
}