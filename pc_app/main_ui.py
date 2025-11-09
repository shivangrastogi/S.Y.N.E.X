# main_ui.py
import sys, os, json
from PyQt5.QtWidgets import QApplication, QStackedWidget, QMessageBox
from auth.login_window import LoginWindow
from auth.register_window import RegisterWindow
from auth.loading_window import LoadingWindow
from auth.engine_manager import engine_manager
from auth.complete_profile_window import CompleteProfileWindow
from auth.setup_wizard import SetupWizard
from auth.engine_manager import VOSK_MODEL_PATH


# DO NOT import ChatWindow here

class MainApp(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS Desktop App")

        engine_manager.load_models_async()

        self.login_page = LoginWindow(
            self.show_register,
            self.handle_login,
            self.show_complete_profile
        )
        self.register_page = RegisterWindow(self.show_login)
        self.loading_page = None
        self.chat_page = None
        self.complete_profile_page = None

        self.addWidget(self.login_page)
        self.addWidget(self.register_page)

        user_data = self.load_user_data()
        if user_data and user_data.get("uid"):
            self.handle_login(user_data)
        else:
            self.setCurrentWidget(self.login_page)

    def load_user_data(self):
        file_path = r"C:\Users\bosss\PycharmProjects\PythonProject\jarvis\PythonProject3\pc_app\user_data.json"
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def show_login(self):
        self.setCurrentWidget(self.login_page)

    def show_register(self):
        self.setCurrentWidget(self.register_page)

    def handle_login(self, user_data):
        if engine_manager.is_models_loaded():
            self.show_chat(user_data)
        else:
            self.show_loading(user_data)

    def show_loading(self, user_data):
        if not self.loading_page:
            self.loading_page = LoadingWindow(user_data)
            self.loading_page.models_loaded_signal.connect(
                lambda: self.show_chat(self.loading_page.user_data)
            )
            self.addWidget(self.loading_page)

        self.loading_page.user_data = user_data
        self.setCurrentWidget(self.loading_page)

    def show_chat(self, user_data):
        if not self.chat_page:
            from chat.chat_window import ChatWindow
            # Pass the new show_logout function
            self.chat_page = ChatWindow(user_data, self.show_logout)
            self.addWidget(self.chat_page)

        self.setCurrentWidget(self.chat_page)

    def show_complete_profile(self, uid, id_token, email, first, last):
        if not self.complete_profile_page:
            self.complete_profile_page = CompleteProfileWindow(
                on_profile_complete=self.handle_login
            )
            self.addWidget(self.complete_profile_page)

        self.complete_profile_page.update_user_info(uid, id_token, email, first, last)
        self.setCurrentWidget(self.complete_profile_page)

    def show_logout(self):
        """Clears session and returns to login page."""
        print("Logging out...")
        # 1. Clear local session file
        file_path = r"C:\Users\bosss\PycharmProjects\PythonProject\jarvis\PythonProject3\pc_app\user_data.json"
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error removing session file: {e}")

        # 2. Destroy the chat page (so a new one is created on next login)
        if self.chat_page:
            self.removeWidget(self.chat_page)
            self.chat_page.deleteLater()
            self.chat_page = None

        # 3. Switch back to the login page
        self.setCurrentWidget(self.login_page)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Check for setup flag
    if "--setup" in sys.argv:
        # Run the Setup Wizard instead of the main app
        wizard = SetupWizard()
        wizard.show()

    else:
        # --- Normal App Startup ---

        # Check if models exist *before* loading
        if not os.path.isdir(VOSK_MODEL_PATH):
            QMessageBox.critical(None, "Error",
                                 "Models not found. Please run the installer again to download them.")
            sys.exit()  # Exit if models are missing

        # Load the QSS stylesheet
        try:
            style_path = "style.qss"
            with open(style_path, "r") as f:
                style = f.read()
                app.setStyleSheet(style)
        except FileNotFoundError:
            print("Stylesheet 'style.qss' not found. Loading with default style.")

        window = MainApp()
        window.showMaximized()

    sys.exit(app.exec_())


# --- This is the new main block to apply style and maximize ---
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#
#     # Load the QSS stylesheet
#     try:
#         # Assuming style.qss is in the same directory as main_ui.py's parent
#         # Adjust path if needed
#         style_path = os.path.join(os.path.dirname(__file__), '..', 'style.qss')
#         # If your style.qss is in pc_app, just use "style.qss"
#         # Let's assume it's in the *parent* folder (D:\OFFICIAL_JARVIS\Personal-Assistant)
#
#         # --- Simpler Path: Assume style.qss is next to main_ui.py ---
#         # If style.qss is in 'pc_app' folder:
#         # style_path = "pc_app/style.qss"
#
#         # Let's assume you put it in the ROOT (Personal-Assistant) folder
#         style_path = "style.qss"
#
#         with open(style_path, "r") as f:
#             style = f.read()
#             app.setStyleSheet(style)
#     except FileNotFoundError:
#         print("Stylesheet 'style.qss' not found. Loading with default style.")
#
#     window = MainApp()
#     window.showMaximized()  # <-- This makes the window fill the screen
#
#     sys.exit(app.exec_())


# # main_ui.py
# import sys, os, json
# from PyQt5.QtWidgets import QApplication, QStackedWidget
# from auth.login_window import LoginWindow
# from auth.register_window import RegisterWindow
# from auth.loading_window import LoadingWindow
# from auth.engine_manager import engine_manager
# # Import the new window
# from auth.complete_profile_window import CompleteProfileWindow
#
#
# # DO NOT import ChatWindow here
#
# class MainApp(QStackedWidget):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("JARVIS Desktop App")
#
#         engine_manager.load_models_async()
#
#         # Pass the new 'show_complete_profile' function to LoginWindow
#         self.login_page = LoginWindow(
#             self.show_register,
#             self.handle_login,
#             self.show_complete_profile
#         )
#         self.register_page = RegisterWindow(self.show_login)
#         self.loading_page = None
#         self.chat_page = None
#         self.complete_profile_page = None  # Add placeholder for new page
#
#         self.addWidget(self.login_page)
#         self.addWidget(self.register_page)
#         # We will add loading_page and chat_page when needed
#
#         user_data = self.load_user_data()
#         if user_data and user_data.get("uid"):
#             self.handle_login(user_data)
#         else:
#             self.setCurrentWidget(self.login_page)
#
#     def load_user_data(self):
#         file_path = r"D:\OFFICIAL_JARVIS\Personal-Assistant\pc_app\user_data.json"
#         if os.path.exists(file_path):
#             try:
#                 with open(file_path, "r") as f:
#                     return json.load(f)
#             except (json.JSONDecodeError, KeyError):
#                 return None
#         return None
#
#     def show_login(self):
#         self.setCurrentWidget(self.login_page)
#
#     def show_register(self):
#         self.setCurrentWidget(self.register_page)
#
#     def handle_login(self, user_data):
#         """This function is now the main entry point to the app after any login."""
#         if engine_manager.is_models_loaded():
#             self.show_chat(user_data)
#         else:
#             self.show_loading(user_data)
#
#     def show_loading(self, user_data):
#         if not self.loading_page:
#             self.loading_page = LoadingWindow(user_data)
#             self.loading_page.models_loaded_signal.connect(
#                 lambda: self.show_chat(self.loading_page.user_data)
#             )
#             self.addWidget(self.loading_page)
#
#         self.loading_page.user_data = user_data
#         self.setCurrentWidget(self.loading_page)
#
#     def show_chat(self, user_data):
#         if not self.chat_page:
#             from chat.chat_window import ChatWindow
#             self.chat_page = ChatWindow(user_data)
#             self.addWidget(self.chat_page)
#
#         self.setCurrentWidget(self.chat_page)
#
#     def show_complete_profile(self, uid, id_token, email, first, last):
#         """Creates or updates the 'Complete Profile' page and displays it."""
#         if not self.complete_profile_page:
#             # Pass 'handle_login' as the "done" callback
#             self.complete_profile_page = CompleteProfileWindow(
#                 on_profile_complete=self.handle_login
#             )
#             self.addWidget(self.complete_profile_page)
#
#         # Update the page with the new user's info
#         self.complete_profile_page.update_user_info(uid, id_token, email, first, last)
#         self.setCurrentWidget(self.complete_profile_page)
#
#
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#
#     # Load the QSS stylesheet
#     try:
#         with open("style.qss", "r") as f:
#             style = f.read()
#             app.setStyleSheet(style)
#     except FileNotFoundError:
#         print("Stylesheet 'style.qss' not found. Loading with default style.")
#
#     window = MainApp()
#     window.showMaximized()  # <-- This makes the window fill the screen
#
#     sys.exit(app.exec_())
#
# # if __name__ == "__main__":
# #     app = QApplication(sys.argv)
# #     window = MainApp()
# #     window.show()
# #     sys.exit(app.exec_())