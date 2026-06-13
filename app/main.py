import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON
from app.core.app_info import APP_NAME
from app.gui.main_window import MainWindow
from app.gui.startup_splash import StartupSplash


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))

    window = MainWindow()
    if window.settings.get("animations_enabled", True):
        splash = StartupSplash(
            play_sound=bool(window.settings.get("sounds_enabled", True)),
            volume=int(window.settings.get("sound_volume", 35)),
        )
        splash.finished.connect(window.show)
        splash.start()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
