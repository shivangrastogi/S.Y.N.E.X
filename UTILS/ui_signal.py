from PyQt5.QtCore import QObject, pyqtSignal

class UiSignals(QObject):
    chatbox = pyqtSignal(str, str)  # sender, message

ui_signals = UiSignals()

def send_to_ui_chatbox(sender, message):
    try:
        ui_signals.chatbox.emit(sender, message)
    except Exception as e:
        print(f"[UI Signal Error] {e}")
