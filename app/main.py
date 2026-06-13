import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON
from app.core.app_info import APP_NAME
from app.core.update_installer import cleanup_stale_update_helpers, run_update_installer_from_args
from app.gui.main_window import MainWindow
from app.gui.startup_splash import StartupSplash


def main():
    installer_result = run_update_installer_from_args(sys.argv[1:])
    if installer_result is not None:
        raise SystemExit(installer_result)
    cleanup_stale_update_helpers()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))

    window = MainWindow()
    if window.settings.get("animations_enabled", True) and window.settings.get("startup_splash_enabled", True):
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
