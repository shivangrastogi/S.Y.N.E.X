import sys
import os

# Add the root directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.dashboard import JarvisDashboard
from PyQt5.QtWidgets import QApplication

def main():
    app = QApplication(sys.argv)
    dashboard = JarvisDashboard()
    dashboard.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
