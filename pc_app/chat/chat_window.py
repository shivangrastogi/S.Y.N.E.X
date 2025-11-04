# chat/chat_window.py
from PyQt5.QtWidgets import QWidget, QTextEdit, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QLabel
from Backend.FUNCTION.SPEAK.speak import JarvisSpeaker
from Backend.FUNCTION.LISTEN.listen import listen
from Backend.BRAIN.processor import execute_command, find_best_match
import threading, json, time


class ChatWindow(QWidget):
    # Add 'on_logout' to the init
    def __init__(self, user_data, on_logout):
        super().__init__()
        self.user_data = user_data
        self.on_logout = on_logout  # Store the logout function

        self.setWindowTitle("JARVIS Assistant")
        self.setGeometry(400, 200, 600, 500)
        self.speaker = JarvisSpeaker()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Add padding
        layout.setSpacing(10)  # Add spacing

        # --- Header with Logout Button ---
        header_layout = QHBoxLayout()

        self.welcome_label = QLabel(f"Welcome, {self.user_data['first_name']}")
        self.welcome_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("logoutButton")  # For styling from QSS
        logout_btn.setFixedWidth(100)  # Give it a fixed width
        logout_btn.clicked.connect(self.on_logout)  # Connect to the passed-in function

        header_layout.addWidget(self.welcome_label)
        header_layout.addStretch()  # Pushes logout button to the right
        header_layout.addWidget(logout_btn)

        layout.addLayout(header_layout)  # Add header to main layout
        # ---------------------------------

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        layout.addWidget(self.chat_area)

        # --- Input Layout (Horizontal) ---
        input_layout = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type your command here...")
        # Handle "Enter" key press in the input field
        self.input.returnPressed.connect(self.handle_input)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.handle_input)
        send_btn.setFixedWidth(100)

        input_layout.addWidget(self.input)
        input_layout.addWidget(send_btn)

        layout.addLayout(input_layout)
        # ---------------------------------

        self.setLayout(layout)

        self.speaker.speak(f"Hello {self.user_data['first_name']}, I am ready to assist you.")
        self.chat_area.append(f"JARVIS: Hello {self.user_data['first_name']}, I am ready to assist you.")

    def handle_input(self):
        query = self.input.text().strip()
        if not query:
            return

        self.chat_area.append(f"You: {query}")
        self.input.clear()

        threading.Thread(target=self.process_query, args=(query,)).start()

    def process_query(self, query):
        key, data = find_best_match(query)
        response = execute_command(key, data)

        if not response:
            response = "Sorry, I didn't understand that."

        self.chat_area.append(f"JARVIS: {response}")
        self.speaker.speak(response)