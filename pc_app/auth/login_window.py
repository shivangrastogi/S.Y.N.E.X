# login_window.py
from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from .firebase_config import auth, db
import json, os

class LoginWindow(QWidget):
    def __init__(self, switch_to_register, switch_to_chat):
        super().__init__()
        self.switch_to_register = switch_to_register
        self.switch_to_chat = switch_to_chat
        self.setWindowTitle("Login - JARVIS")
        self.setGeometry(500, 250, 400, 300)
        self.initUI()

    def initUI(self):
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

        register_link = QPushButton("Create a new account")
        register_link.clicked.connect(self.switch_to_register)
        layout.addWidget(register_link)

        self.setLayout(layout)

    def login(self):
        email = self.email.text().strip()
        password = self.password.text().strip()

        if not email or not password:
            QMessageBox.warning(self, "Error", "Please enter email and password.")
            return

        try:
            user = auth.sign_in_with_email_and_password(email, password)
            uid = user["localId"]
            user_data = db.child("users").child(uid).get().val()

            with open("pc_app/user_data.json", "w") as f:
                json.dump({"uid": uid, **user_data}, f)

            QMessageBox.information(self, "Success", f"Welcome {user_data['first_name']}!")
            self.switch_to_chat()

        except Exception as e:
            QMessageBox.warning(self, "Login Failed", str(e))
