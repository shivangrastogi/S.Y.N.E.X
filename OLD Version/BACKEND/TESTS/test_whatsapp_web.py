from AUTOMATION.Modules.GoogleAuth import google_login
from AUTOMATION.Modules.GoogleContactsSync import fetch_and_save_contacts
from AUTOMATION.Modules.UserProfileManager import create_profile, profile_exists

if not profile_exists():
    print("🔐 Logging in with Google...")
    google_data = google_login()

    preferred = input(
        f"What should I call you? (Default: {google_data['full_name']}): "
    ).strip() or google_data["full_name"]

    create_profile(google_data, preferred)

    print("📒 Fetching contacts...")
    fetch_and_save_contacts()

    print("✅ Setup complete")
else:
    print("User already initialized.")
