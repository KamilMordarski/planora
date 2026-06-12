import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON
from app.core.app_info import APP_NAME
from app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
