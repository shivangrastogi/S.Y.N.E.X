import sys, os, json
from PyQt5.QtWidgets import QApplication, QStackedWidget
from auth.login_window import LoginWindow
from auth.register_window import RegisterWindow
from chat.chat_window import ChatWindow

class MainApp(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS Desktop App")

        self.login_page = LoginWindow(self.show_register, self.show_chat)
        self.register_page = RegisterWindow(self.show_login)
        self.chat_page = ChatWindow()

        self.addWidget(self.login_page)
        self.addWidget(self.register_page)
        self.addWidget(self.chat_page)

        if os.path.exists("pc_app/user_data.json"):
            self.setCurrentWidget(self.chat_page)
        else:
            self.setCurrentWidget(self.login_page)

    def show_login(self):
        self.setCurrentWidget(self.login_page)

    def show_register(self):
        self.setCurrentWidget(self.register_page)

    def show_chat(self):
        self.chat_page = ChatWindow()
        self.addWidget(self.chat_page)
        self.setCurrentWidget(self.chat_page)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
