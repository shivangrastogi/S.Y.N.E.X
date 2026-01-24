import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore

# Path to your Firebase config JSON (client)
firebase_config = {
  "apiKey": "AIzaSyCGW8ssB7vKau3Uchx_K0P0Ca52SknLSGo", 
  "authDomain": "jarvis-remote-6f460.firebaseapp.com",
  "databaseURL": "https://jarvis-remote-6f460-default-rtdb.firebaseio.com", 
  "projectId": "jarvis-remote-6f460",
  "storageBucket": "jarvis-remote-6f460.firebasestorage.app",
  "messagingSenderId": "674383759043",
  "appId": "1:674383759043:web:38cf8b7cad8139958bc476",
  "measurementId": "G-BQPENBYK2S"
}

firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

# Admin SDK (for DB or verification)
cred = credentials.Certificate(r"C:\Users\bosss\Downloads\Personal-Assistant-main\Personal-Assistant\Backend\DATA\FIREBASE\serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def register_user(email, password):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        print(f"✅ User registered successfully: {email}")
        return user
    except Exception as e:
        print("❌ Registration failed:", e)
        return None

def login_user(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        print(f"✅ Logged in as: {email}")
        return user
    except Exception as e:
        print("❌ Login failed:", e)
        return None

def save_user_data(uid, data):
    try:
        db.collection("users").document(uid).set(data, merge=True)
        print("✅ User data saved in Firestore.")
    except Exception as e:
        print("❌ Failed to save data:", e)
