# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/dashboard/tabs/automation_tab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QTimeEdit, QPushButton, QListWidget, QListWidgetItem
from PyQt5.QtCore import QTime

class AutomationTab(QWidget):
    """
    Scheduler and Automation view - handles timed tasks and post scheduling.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        header = QLabel("Automations & Scheduling")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(header)

        # Input Area
        input_layout = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Task description (e.g., Post to GitHub)")
        self.time_input = QTimeEdit(QTime.currentTime())
        
        self.add_btn = QPushButton("Schedule Task")
        self.add_btn.setStyleSheet("background-color: #00ff88; color: #000000; font-weight: bold;")
        self.add_btn.clicked.connect(self._add_task)

        input_layout.addWidget(self.task_input)
        input_layout.addWidget(self.time_input)
        input_layout.addWidget(self.add_btn)

        layout.addLayout(input_layout)

        # Active Tasks List
        self.task_list = QListWidget()
        self.task_list.setStyleSheet("background-color: #2b2d31; border-radius: 6px; margin-top: 20px;")
        layout.addWidget(self.task_list)

        layout.addStretch()

    def _add_task(self):
        task = self.task_input.text().strip()
        time_str = self.time_input.time().toString("hh:mm AP")
        if task:
            item = QListWidgetItem(f"[{time_str}] {task}")
            self.task_list.addItem(item)
            self.task_input.clear()
            # In a real implementation, this would fire an event to the background scheduler
