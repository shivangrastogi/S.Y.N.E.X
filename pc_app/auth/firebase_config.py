# auth/firebase_config.py
import os
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore

# --- Pyrebase (Client) Setup ---
# This is for Auth and Realtime DB
firebaseConfig = {
    "apiKey": "AIzaSyCGW8ssB7vKau3Uchx_K0P0Ca52SknLSGo",
    "authDomain": "jarvis-remote-6f460.firebaseapp.com",
    "databaseURL": "https://jarvis-remote-6f460-default-rtdb.firebaseio.com",
    "projectId": "jarvis-remote-6f460",
    "storageBucket": "jarvis-remote-6f460.firebasestorage.app",
    "messagingSenderId": "674383759043",
    "appId": "1:674383759043:web:38cf8b7cad8139958bc476",
    "measurementId": "G-BQPENBYK2S"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()  # Realtime DB

# --- Firebase-Admin (Server) Setup ---
# This is for Firestore (db_firestore)

# This check prevents the "ValueError: The default Firebase app already exists."
if not firebase_admin._apps:
    try:
        # Use relative path from pc_app/auth directory
        auth_dir = os.path.dirname(os.path.abspath(__file__))
        pc_app_dir = os.path.dirname(auth_dir)
        backend_dir = os.path.join(os.path.dirname(pc_app_dir), "BACKEND")
        service_account_path = os.path.join(backend_dir, "DATA", "FIREBASE", "serviceAccount.json")
        
        if os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
        else:
            print(f"Warning: serviceAccount.json not found at {service_account_path}")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Firebase Admin SDK: {e}")
        # You might want to handle this more gracefully

try:
    db_firestore = firestore.client()  # Firestore client
except Exception as e:
    print(f"Warning: Could not initialize Firestore client: {e}")
    db_firestore = None
