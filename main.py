import sys
import logging
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import AdbFileBrowser

# Setup logging
logging.basicConfig(
    filename='adb_file_browser.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    app = QApplication(sys.argv)
    window = AdbFileBrowser()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()