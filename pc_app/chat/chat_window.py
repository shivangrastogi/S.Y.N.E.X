# chat_window.py
from PyQt5.QtWidgets import QWidget, QTextEdit, QLineEdit, QPushButton, QVBoxLayout, QLabel
from FUNCTION.SPEAK.speak import JarvisSpeaker
from FUNCTION.LISTEN.listen import listen
from BRAIN.processor import execute_command, find_best_match
import threading, json, time

class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS Assistant")
        self.setGeometry(400, 200, 600, 500)
        self.speaker = JarvisSpeaker()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        layout.addWidget(self.chat_area)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type your command here...")
        layout.addWidget(self.input)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.handle_input)
        layout.addWidget(send_btn)

        self.setLayout(layout)

        with open(r"D:\OFFICIAL_JARVIS\Personal-Assistant\pc_app\user_data.json", "r") as f:
            data = json.load(f)
        self.username = data["first_name"]
        self.speaker.speak(f"Hello {self.username}, I am ready to assist you.")
        self.chat_area.append(f"JARVIS: Hello {self.username}, I am ready to assist you.")

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
