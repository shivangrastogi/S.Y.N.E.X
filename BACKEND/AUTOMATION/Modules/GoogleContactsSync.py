import re

import requests
import json
import os

from google.oauth2.credentials import Credentials
from CORE.Utils.DataPath import get_data_file_path

TOKEN_PATH = get_data_file_path("USER", "google_token.json")
CONTACT_FILE = get_data_file_path("USER", "contacts.json")

PEOPLE_API_URL = "https://people.googleapis.com/v1/people/me/connections"


def normalize_phone_number(raw: str, default_country="+91"):
    """
    Converts phone numbers to WhatsApp-compatible E.164 format.
    """
    if not raw:
        return None

    # Remove everything except digits and +
    cleaned = re.sub(r"[^\d+]", "", raw)

    # Already in international format
    if cleaned.startswith("+") and len(cleaned) >= 11:
        return cleaned

    # Indian local number (10 digits)
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) == 10:
        return default_country + digits_only

    # Unsupported format
    return None


def fetch_and_save_contacts():
    """
    Fetch Google contacts and save to contacts.json
    """

    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError("Google token not found. Please login first.")

    creds = Credentials.from_authorized_user_file(
        TOKEN_PATH,
        scopes=["https://www.googleapis.com/auth/contacts.readonly"]
    )

    headers = {
        "Authorization": f"Bearer {creds.token}"
    }

    params = {
        "personFields": "names,phoneNumbers",
        "pageSize": 1000
    }

    response = requests.get(PEOPLE_API_URL, headers=headers, params=params)

    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch contacts: {response.text}")

    data = response.json()

    contacts = {}

    for person in data.get("connections", []):
        names = person.get("names", [])
        phones = person.get("phoneNumbers", [])

        if not names or not phones:
            continue

        name = names[0].get("displayName", "").strip()
        raw_phone = phones[0].get("value", "")

        phone = normalize_phone_number(raw_phone)

        if name and phone:
            contacts[name.lower()] = phone


    with open(CONTACT_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=4, ensure_ascii=False)

    print(f"✅ Saved {len(contacts)} contacts to contacts.json")
    return contacts
