# auth/firebase_config.py

import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore

# --- Pyrebase (Client) Setup ---
# This is for Auth and Realtime DB (in your setup)
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
        cred = credentials.Certificate(r"C:\Users\bosss\PycharmProjects\PythonProject\jarvis\PythonProject3\BACKEND\DATA\FIREBASE\serviceAccount.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Firebase Admin SDK: {e}")
        # You might want to handle this more gracefully

db_firestore = firestore.client()  # Firestore client

# Your original file had 'auth = firebase.auth()' at the end.
# This was redundant, as it's already set on line 18.
# The 'auth' object from pyrebase is correctly used by your login/register windows.