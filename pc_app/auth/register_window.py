from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from .firebase_config import auth, db
import json

class RegisterWindow(QWidget):
    def __init__(self, switch_to_login):
        super().__init__()
        self.switch_to_login = switch_to_login
        self.setWindowTitle("Register - JARVIS")
        self.setGeometry(500, 250, 400, 350)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("First Name")
        layout.addWidget(self.first_name)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("Last Name")
        layout.addWidget(self.last_name)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        layout.addWidget(self.email)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password")
        layout.addWidget(self.password)

        register_btn = QPushButton("Register")
        register_btn.clicked.connect(self.register)
        layout.addWidget(register_btn)

        login_link = QPushButton("Already have an account? Login")
        login_link.clicked.connect(self.switch_to_login)
        layout.addWidget(login_link)

        self.setLayout(layout)

    def register(self):
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        email = self.email.text().strip()
        password = self.password.text().strip()

        if not all([first, last, email, password]):
            QMessageBox.warning(self, "Error", "Please fill all fields.")
            return

        try:
            user = auth.create_user_with_email_and_password(email, password)
            uid = user["localId"]
            db.child("users").child(uid).set({
                "first_name": first,
                "last_name": last,
                "email": email
            })

            with open("pc_app/user_data.json", "w") as f:
                json.dump({"uid": uid, "first_name": first, "last_name": last, "email": email}, f)

            QMessageBox.information(self, "Success", "Registration successful!")
            self.switch_to_login()

        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
