# auth/login_window.py
from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QLabel
from PyQt5.QtCore import Qt
from auth.firebase_config import auth, db, db_firestore
import json
import os
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import webbrowser


class LoginWindow(QWidget):
    def __init__(self, switch_to_register, switch_to_chat, switch_to_complete_profile):  # Added new callback
        super().__init__()
        self.switch_to_register = switch_to_register
        self.switch_to_chat = switch_to_chat
        self.switch_to_complete_profile = switch_to_complete_profile  # Store the new callback

        self.setWindowTitle("Login - JARVIS")
        self.setGeometry(500, 250, 400, 350)
        self.FIREBASE_WEB_API_KEY = "AIzaSyCGW8ssB7vKau3Uchx_K0P0Ca52SknLSGo"
        self.initUI()

    def initUI(self):
        # ... (this function is exactly the same, no changes needed) ...
        layout = QVBoxLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        layout.addWidget(self.email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password")
        layout.addWidget(self.password)
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        forgot_btn = QPushButton("Forgot Password?")
        forgot_btn.clicked.connect(self.forgot_password)
        layout.addWidget(forgot_btn)
        or_label = QLabel("or")
        or_label.setAlignment(Qt.AlignCenter)
        or_label.setObjectName("orLabel")
        layout.addWidget(or_label)
        google_login_btn = QPushButton("Sign In with Google")
        google_login_btn.setStyleSheet("background-color: #4285F4; color: white;")
        google_login_btn.setObjectName("googleButton")
        google_login_btn.clicked.connect(self.login_with_google)
        layout.addWidget(google_login_btn)
        register_link = QPushButton("Create a new account")
        register_link.clicked.connect(self.switch_to_register)
        layout.addWidget(register_link)
        self.setLayout(layout)

    def login(self):
        # ... (this function is exactly the same, no changes needed) ...
        email = self.email.text().strip()
        password = self.password.text().strip()
        if not email or not password:
            QMessageBox.warning(self, "Error", "Please enter email and password.")
            return
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            uid = user["localId"]
            id_token = user["idToken"]
            if 'db_firestore' in globals() and db_firestore:
                user_doc = db_firestore.collection('users').document(uid).get()
                user_data = user_doc.to_dict() if user_doc.exists else None
            else:
                user_data = db.child("users").child(uid).get(token=id_token).val()
            if not user_data:
                QMessageBox.warning(self, "Error", "User data not found in Firebase.")
                return
            session_data = {"uid": uid, **user_data, "idToken": id_token}
            self.save_local_session(session_data)
            QMessageBox.information(self, "Success", f"Welcome {user_data['first_name']}!")
            self.switch_to_chat(user_data)
        except Exception as e:
            QMessageBox.warning(self, "Login Failed", str(e))

    def login_with_google(self):
        try:
            # 1. Authenticate with Google
            flow = InstalledAppFlow.from_client_secrets_file(
                "auth/client_secrets.json",
                scopes=["https://www.googleapis.com/auth/userinfo.profile",
                        "https://www.googleapis.com/auth/userinfo.email",
                        "openid"]
            )
            creds = flow.run_local_server(port=0)
            google_id_token = creds.id_token

            # 2. Exchange Google Token for a Firebase Token
            firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={self.FIREBASE_WEB_API_KEY}"
            payload = {
                "postBody": f"id_token={google_id_token}&providerId=google.com",
                "requestUri": "http://localhost",
                "returnIdpCredential": True,
                "returnSecureToken": True
            }
            response = requests.post(firebase_url, json=payload)
            response_data = response.json()

            if not response.ok:
                raise Exception(f"Firebase Error: {response_data['error']['message']}")

            # 3. Get Firebase user info
            uid = response_data["localId"]
            firebase_id_token = response_data["idToken"]
            email = response_data["email"]

            # --- NEW LOGIC HERE ---

            # 4. Check if user exists in our *database*
            if 'db_firestore' in globals() and db_firestore:
                user_doc = db_firestore.collection('users').document(uid).get()
                user_data = user_doc.to_dict() if user_doc.exists else None
            else:
                user_data = db.child("users").child(uid).get(token=firebase_id_token).val()

            if user_data:
                # User exists in Auth AND Database, proceed to chat
                session_data = {"uid": uid, **user_data, "idToken": firebase_id_token}
                self.save_local_session(session_data)
                QMessageBox.information(self, "Success", f"Welcome {user_data['first_name']}!")
                self.switch_to_chat(user_data)
            else:
                # New user OR existing user with no DB entry
                # Get default names from Google and send to complete profile page
                first_name = response_data.get("firstName", response_data.get("displayName", "")).split(" ")[0]
                last_name = response_data.get("lastName", "")

                # Call the new callback function for main_ui
                self.switch_to_complete_profile(uid, firebase_id_token, email, first_name, last_name)

        except Exception as e:
            QMessageBox.warning(self, "Google Login Failed", str(e))

    def save_local_session(self, user_data_with_token):
        """Saves user data and tokens to the local JSON file."""
        os.makedirs("pc_app", exist_ok=True)
        file_path = r"D:\OFFICIAL_JARVIS\Personal-Assistant\pc_app\user_data.json"
        with open(file_path, "w") as f:
            json.dump(user_data_with_token, f)

    def forgot_password(self):
        # ... (this function is exactly the same, no changes needed) ...
        email = self.email.text().strip()
        if not email:
            QMessageBox.warning(self, "Error", "Please enter your email to reset password.")
            return
        try:
            auth.send_password_reset_email(email)
            QMessageBox.information(self, "Success", "Password reset email sent!")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))