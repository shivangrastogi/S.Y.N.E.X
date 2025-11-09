# auth/complete_profile_window.py
import os
import json
from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QLabel
from .firebase_config import db, db_firestore  # Import your db and firestore


class CompleteProfileWindow(QWidget):
    def __init__(self, on_profile_complete):
        super().__init__()
        self.on_profile_complete = on_profile_complete  # This is the handle_login function

        # We will store user info temporarily
        self.uid = None
        self.id_token = None
        self.email = None

        self.setWindowTitle("Complete Your Profile - JARVIS")
        self.setGeometry(500, 250, 400, 250)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        info_label = QLabel("Welcome! Please confirm your name to continue.")
        layout.addWidget(info_label)

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("First Name")
        layout.addWidget(self.first_name_input)

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Last Name")
        layout.addWidget(self.last_name_input)

        save_btn = QPushButton("Save and Continue")
        save_btn.clicked.connect(self.save_profile)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def update_user_info(self, uid, id_token, email, first, last):
        """Called by main_ui to pass in the new user's data"""
        self.uid = uid
        self.id_token = id_token
        self.email = email
        self.first_name_input.setText(first)
        self.last_name_input.setText(last)

    def save_profile(self):
        first = self.first_name_input.text().strip()
        last = self.last_name_input.text().strip()

        if not first or not last:
            QMessageBox.warning(self, "Error", "Please fill in all fields.")
            return

        user_data = {
            "first_name": first,
            "last_name": last,
            "email": self.email
        }

        try:
            # 1. Save to Firebase Database
            if 'db_firestore' in globals() and db_firestore:
                db_firestore.collection('users').document(self.uid).set(user_data)
            else:
                db.child("users").child(self.uid).set(user_data, token=self.id_token)

            # 2. Save to local session file
            session_data = {"uid": self.uid, **user_data, "idToken": self.id_token}
            self.save_local_session(session_data)

            # 3. Tell main_ui to proceed to chat
            QMessageBox.information(self, "Success", f"Welcome, {first}!")
            self.on_profile_complete(user_data)  # This triggers handle_login

        except Exception as e:
            QMessageBox.warning(self, "Error Saving Profile", str(e))

    def save_local_session(self, user_data_with_token):
        """Saves user data and tokens to the local JSON file."""
        os.makedirs("pc_app", exist_ok=True)
        file_path = r"C:\Users\bosss\PycharmProjects\PythonProject\jarvis\PythonProject3\pc_app\user_data.json"
        with open(file_path, "w") as f:
            json.dump(user_data_with_token, f)