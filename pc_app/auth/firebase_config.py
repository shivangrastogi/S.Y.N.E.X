# firebase_config.py
# Option 1: Keep Realtime DB (current setup)
import pyrebase

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

# Option 2: Switch to Firestore (recommended for user data)
# Install: pip install firebase-admin
# Download your Firebase service account key JSON from Firebase Console > Project Settings > Service Accounts
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("D:\OFFICIAL_JARVIS\Personal-Assistant\Backend\DATA\FIREBASE\serviceAccount.json")  # Replace with your key file path
firebase_admin.initialize_app(cred)
db_firestore = firestore.client()  # Firestore client
auth = firebase.auth()  # Still use pyrebase for auth, or switch to firebase-admin for auth too