import json
import os
from CORE.Utils.DataPath import get_data_file_path

PROFILE_PATH = get_data_file_path("USER", "user_profile.json")


def profile_exists():
    return os.path.exists(PROFILE_PATH)


def load_profile():
    if not profile_exists():
        return None
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def create_profile(google_data, preferred_name):
    profile = {
        "google_id": google_data["google_id"],
        "email": google_data["email"],
        "full_name": google_data["full_name"],
        "preferred_name": preferred_name
    }

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=4)
