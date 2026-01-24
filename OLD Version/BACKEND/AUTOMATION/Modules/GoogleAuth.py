from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import requests
import json
import os

from CORE.Utils.DataPath import get_data_file_path


# ✅ Correct, normalized scopes (NO warnings)
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/contacts.readonly",
]

# ✅ Paths
TOKEN_PATH = get_data_file_path("USER", "google_token.json")
CLIENT_SECRET = get_data_file_path("CONFIG", "google_client_secret.json")


def google_login():
    """
    Handles Google OAuth login.
    - Reuses token if available
    - Prompts browser only on first run
    - Returns basic user profile
    """

    creds = None

    # 🔁 Load existing token if present
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # 🔐 If no valid credentials → login
    if not creds or not creds.valid:
        print("🔐 Logging in with Google...")

        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET,
            scopes=SCOPES
        )

        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="Please authorize Jarvis to access your Google account",
            success_message="✅ Login successful. You may close this window.",
            open_browser=True
        )

        # 💾 Save token for future runs
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    # 👤 Fetch user profile
    profile = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"}
    ).json()

    return {
        "google_id": profile.get("id"),
        "email": profile.get("email"),
        "full_name": profile.get("name")
    }
