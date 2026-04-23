import sys
from ui.dashboard import JarvisDashboard
from PyQt5.QtWidgets import QApplication

def main():
    print("Starting A.E.R.I.S v3.0...")
    app = QApplication(sys.argv)
    
    # Initialize UI
    window = JarvisDashboard()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
