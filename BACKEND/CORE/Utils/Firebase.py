# CORE/TTS_Control.py

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
import time

# from CORE.Utils.DataPath import get_data_file_path

# --- CONFIGURATION ---
# IMPORTANT: Update this path to where you placed your downloaded JSON key
SERVICE_ACCOUNT_PATH = r'BACKEND/DATA/CONFIG/FIREBASE/jarvisv1-c40ed-adminsdk.json'

# Global reference for Firestore client
db = None


def init_firebase_logger():
    """Initializes the Firebase Admin SDK and Firestore client once."""
    global db
    if firebase_admin._apps:
        # Already initialized
        db = firestore.client()
        return

    try:
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            raise FileNotFoundError("Firebase Service Account Key not found!")

        # Initialize the app using the service account certificate
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)

        db = firestore.client()
        print("✅ Firebase Firestore Logger initialized.")
    except Exception as e:
        db = None
        print(f"❌ FIREBASE INIT ERROR (Logging disabled): {e}")


def log_uncertain_query(log_data: dict, status_level: str):
    """Pushes structured log data to Firestore if the database is initialized."""
    if not db:
        return

    # 1. Add required metadata
    log_data['timestamp_ms'] = int(time.time() * 1000)
    log_data['log_level'] = status_level

    try:
        # Push to the 'jarvis_nlu_logs' collection
        db.collection('jarvis_nlu_logs').add(log_data)
        # print(f"📝 Logged to Firestore: {status_level}") # Optional print for verification

    except Exception as e:
        # Log failure silently in a production executable
        print(f"❌ Firestore write failed during runtime: {e}")
        pass