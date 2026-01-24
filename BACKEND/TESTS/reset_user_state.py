import os
from CORE.Utils.DataPath import get_data_file_path

FILES = [
    "google_token.json",
    "contacts.json",
    "user_profile.json"
]

def reset_user_state():
    print("🧹 Resetting USER state...")
    for file in FILES:
        path = get_data_file_path("USER", file)
        if os.path.exists(path):
            os.remove(path)
            print(f"  ✔ Deleted {file}")
    print("✅ USER state reset complete\n")
