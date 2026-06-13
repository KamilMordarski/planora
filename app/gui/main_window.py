import copy
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from app.config import APP_ICON, UPDATE_URL, USER_DATA_DIR
from app.core.app_info import APP_NAME, APP_VERSION
from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry
from app.core.updater import UpdateChecker, UpdateCheckError
from app.gui.home_screen import HomeScreen
from app.gui.guide_dialog import GuideDialog
from app.gui.people_dialog import PeopleDialog
from app.gui.schedule_type_screen import ScheduleTypeScreen
from app.gui.settings_dialog import SettingsDialog
from app.gui.animated_stack import AnimatedStackedWidget
from app.gui.theme_manager import build_stylesheet
from app.gui.ui_feedback import UiFeedback


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ProjectIO.ensure_user_data()
        self.people = ProjectIO.load_people()
        self.settings = ProjectIO.load_settings()
        self.editor = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1360, 840)
        self.setMinimumSize(760, 560)
        if APP_ICON.exists():
            self.setWindowIcon(QIcon(str(APP_ICON)))

        self.stack = AnimatedStackedWidget(lambda: bool(self.settings.get("animations_enabled", True)))
        self.setCentralWidget(self.stack)
        self.home = HomeScreen(
            self.show_schedule_types,
            self.open_project,
            self.edit_people,
            self.check_updates,
            self.open_settings,
            self.open_guide,
        )
        self.schedule_types = ScheduleTypeScreen(
            TemplateRegistry.all(),
            self.create_project,
            self.show_home,
        )
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.schedule_types)
        self.show_home()
        self._apply_style()
        self.ui_feedback = UiFeedback(self.settings, self)
        QApplication.instance().installEventFilter(self.ui_feedback)

        if self.settings.get("check_updates_on_start"):
            QTimer.singleShot(500, lambda: self.check_updates(quiet_if_current=True))

    def _apply_style(self):
        QApplication.instance().setStyleSheet(build_stylesheet(self.settings))

    def show_home(self):
        self.stack.setCurrentWidgetAnimated(self.home)

    def show_schedule_types(self):
        self.stack.setCurrentWidgetAnimated(self.schedule_types)

    def create_project(self, template_id: str):
        template = TemplateRegistry.get(template_id)
        if template:
            self.open_editor(template, copy.deepcopy(template.default_project))

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Otwórz projekt",
            str(USER_DATA_DIR),
            "Projekt JSON (*.json)",
        )
        if not path:
            return
        try:
            project = ProjectIO.load_project(Path(path))
            template = TemplateRegistry.for_project(project)
            if not template:
                raise ValueError(f"Brak szablonu o ID: {project.get('template_id')}")
            self.open_editor(template, project, Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, "Nie można otworzyć projektu", str(exc))

    def open_editor(self, template, project: dict, path: Path | None = None):
        if self.editor is not None:
            self.stack.removeWidget(self.editor)
            self.editor.deleteLater()
        self.editor = template.editor_class(
            project=project,
            people=self.people,
            renderer_class=template.renderer_class,
            project_path=path,
            go_back=self.show_home,
            edit_people=self.edit_people,
            animations_enabled=lambda: bool(self.settings.get("animations_enabled", True)),
        )
        self.stack.addWidget(self.editor)
        self.stack.setCurrentWidgetAnimated(self.editor)

    def edit_people(self):
        dialog = PeopleDialog(self.people, self)
        if dialog.exec():
            self.people = dialog.people
            ProjectIO.save_people(self.people)
            if self.editor is not None:
                self.editor.set_people(self.people)

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings.update(dialog.values())
            ProjectIO.save_settings(self.settings)
            self._apply_style()

    def open_guide(self):
        GuideDialog(self).exec()

    def check_updates(self, quiet_if_current: bool = False):
        checker = UpdateChecker(UPDATE_URL)
        try:
            available = checker.check_for_updates()
        except UpdateCheckError as exc:
            QMessageBox.warning(self, "Aktualizacje", str(exc))
            return

        info = checker.get_update_info() or {}
        if not available:
            if not quiet_if_current:
                QMessageBox.information(self, "Aktualizacje", "Masz najnowszą wersję aplikacji.")
            return

        notes = info.get("notes", [])
        notes_text = "\n".join(f"• {note}" for note in notes) if isinstance(notes, list) else str(notes)
        message = QMessageBox(self)
        message.setWindowTitle("Dostępna aktualizacja")
        message.setIcon(QMessageBox.Information)
        message.setText(f"Dostępna jest wersja {info.get('latest_version')}.")
        message.setInformativeText(f"Data wydania: {info.get('release_date', 'brak')}\n\n{notes_text}")
        download = message.addButton("Otwórz stronę pobierania", QMessageBox.AcceptRole)
        message.addButton(QMessageBox.Close)
        message.exec()
        if message.clickedButton() is download and info.get("download_url"):
            QDesktopServices.openUrl(QUrl(str(info["download_url"])))
