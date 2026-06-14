import copy
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QProgressDialog

from app.config import APP_ICON, AUTOSAVE_FILE, UPDATE_DIR, UPDATE_URL, USER_DATA_DIR
from app.core.app_info import APP_NAME, APP_VERSION
from app.core.people_roles import ROLE_OPTIONS, eligible_people
from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry
from app.core.updater import (
    UpdateChecker,
    UpdateCheckError,
    UpdateDownloadCancelled,
    UpdateDownloadError,
)
from app.core.update_installer import (
    UpdateInstallError,
    consume_update_result,
    is_install_supported,
    launch_update_installer,
)
from app.gui.home_screen import HomeScreen
from app.gui.guide_dialog import GuideDialog
from app.gui.people_dialog import PeopleDialog
from app.gui.planning_tools_dialog import PlanningToolsDialog
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
        self.people_profiles = ProjectIO.load_people_profiles(self.people)
        self.settings = ProjectIO.load_settings()
        self.editor = None
        self._startup_update_scheduled = False
        self._recovery_checked = False
        self._pending_update_result = consume_update_result()

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
            self.open_planning_tools,
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
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(20_000)
        self.autosave_timer.timeout.connect(self.autosave_project)
        self.autosave_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_update_result:
            result = self._pending_update_result
            self._pending_update_result = None
            QTimer.singleShot(700, lambda: self._show_update_result(result))
        if self.settings.get("check_updates_on_start") and not self._startup_update_scheduled:
            self._startup_update_scheduled = True
            QTimer.singleShot(500, lambda: self.check_updates(quiet_if_current=True))
        if not self._recovery_checked:
            self._recovery_checked = True
            QTimer.singleShot(900, self.offer_recovery)

    def _apply_style(self):
        app = QApplication.instance()
        app.setProperty("animationSpeed", self.settings.get("animation_speed", 100))
        app.setStyleSheet(build_stylesheet(self.settings))

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
        editor_people = self.people
        if template.id == "service_meetings":
            editor_people = eligible_people(self.people, self.people_profiles, "service_conductor")
        self.editor = template.editor_class(
            project=project,
            people=editor_people,
            renderer_class=template.renderer_class,
            project_path=path,
            go_back=self.show_home,
            edit_people=self.edit_people,
            animations_enabled=lambda: bool(self.settings.get("animations_enabled", True)),
        )
        self.stack.addWidget(self.editor)
        self._apply_role_filters(template.id)
        self.stack.setCurrentWidgetAnimated(self.editor)

    def edit_people(self):
        dialog = PeopleDialog(self.people, self.people_profiles, self)
        if dialog.exec():
            self.people = dialog.people
            self.people_profiles = dialog.profiles
            ProjectIO.save_people(self.people)
            ProjectIO.save_people_profiles(self.people_profiles)
            if self.editor is not None:
                template = TemplateRegistry.for_project(self.editor.project)
                editor_people = self.people
                if template and template.id == "service_meetings":
                    editor_people = eligible_people(self.people, self.people_profiles, "service_conductor")
                self.editor.set_people(editor_people)
                if template:
                    self._apply_role_filters(template.id)

    def _apply_role_filters(self, template_id: str):
        if self.editor is None:
            return

        def apply(combo, role):
            if combo is None:
                return
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems(eligible_people(self.people, self.people_profiles, role))
            combo.setCurrentText(current)
            combo.setToolTip(f"Lista według roli: {ROLE_OPTIONS[role]}. Nadal możesz wpisać inną osobę ręcznie.")
            combo.blockSignals(False)

        if template_id == "cleaning_attendants":
            apply(self.editor.cleaning_person, "cleaning")
            apply(self.editor.console_person, "console")
            apply(self.editor.microphone_1, "microphone")
            apply(self.editor.microphone_2, "microphone")
            apply(self.editor.lobby_attendant, "attendant")
            apply(self.editor.hall_attendant, "attendant")
        elif template_id == "public_talk_watchtower":
            fields = self.editor.combo_fields
            apply(fields.get("chairman"), "chairman")
            apply(fields.get("lecturer"), "public_speaker")
            apply(fields.get("watchtower_conductor"), "watchtower_conductor")
            apply(fields.get("reader"), "reader")
        elif template_id == "midweek_meeting":
            apply(self.editor.chairman, "chairman")
            apply(self.editor.item_person_1, "midweek_participant")
            apply(self.editor.item_person_2, "midweek_participant")

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings.update(dialog.values())
            ProjectIO.save_settings(self.settings)
            self._apply_style()

    def open_guide(self):
        GuideDialog(self).exec()

    def open_planning_tools(self):
        PlanningToolsDialog(
            self.people,
            self.people_profiles,
            self.current_project,
            self.open_generated_project,
            self.refresh_editor_after_tools,
            self,
        ).exec()

    def current_project(self):
        return self.editor.project if self.editor is not None else None

    def open_generated_project(self, project):
        template = TemplateRegistry.for_project(project)
        if template:
            self.open_editor(template, project)

    def refresh_editor_after_tools(self):
        if self.editor is None:
            return
        project = self.editor.project
        path = self.editor.project_path
        template = TemplateRegistry.for_project(project)
        if template:
            self.open_editor(template, project, path)

    def autosave_project(self):
        project = self.current_project()
        if project:
            try:
                ProjectIO.save_project(AUTOSAVE_FILE, project)
            except OSError:
                pass

    def offer_recovery(self):
        if not AUTOSAVE_FILE.exists() or self.editor is not None:
            return
        answer = QMessageBox.question(
            self,
            "Odzyskać projekt?",
            "Znaleziono automatyczną kopię projektu po poprzedniej sesji. Czy chcesz ją otworzyć?",
        )
        if answer == QMessageBox.Yes:
            try:
                project = ProjectIO.load_project(AUTOSAVE_FILE)
                template = TemplateRegistry.for_project(project)
                if template:
                    self.open_editor(template, project)
            except ValueError as exc:
                QMessageBox.warning(self, "Nie można odzyskać projektu", str(exc))
        else:
            AUTOSAVE_FILE.unlink(missing_ok=True)

    def closeEvent(self, event):
        AUTOSAVE_FILE.unlink(missing_ok=True)
        super().closeEvent(event)

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
        install_supported = is_install_supported()
        action_label = "Pobierz i zainstaluj" if install_supported else "Pobierz aktualizację"
        if install_supported:
            message.setInformativeText(
                f"Data wydania: {info.get('release_date', 'brak')}\n\n{notes_text}\n\n"
                "Planora zostanie zamknięta, zaktualizowana i uruchomiona ponownie. "
                "Przed kontynuowaniem zapisz otwarty projekt."
            )
        download = message.addButton(action_label, QMessageBox.AcceptRole)
        message.addButton(QMessageBox.Close)
        message.exec()
        if message.clickedButton() is download:
            self.download_update(checker)

    def download_update(self, checker: UpdateChecker):
        install_supported = is_install_supported()
        if install_supported:
            UPDATE_DIR.mkdir(parents=True, exist_ok=True)
            path = UPDATE_DIR / checker.suggested_filename()
        else:
            default_path = Path.home() / "Downloads" / checker.suggested_filename()
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Zapisz aktualizację Planory",
                str(default_path),
                "Archiwum ZIP (*.zip);;Wszystkie pliki (*)",
            )
            if not selected_path:
                return
            path = Path(selected_path)

        progress = QProgressDialog("Pobieranie aktualizacji...", "Anuluj", 0, 100, self)
        progress.setWindowTitle("Aktualizacja Planory")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)

        def update_progress(downloaded: int, total: int) -> bool:
            if total:
                progress.setRange(0, 100)
                progress.setValue(min(100, round(downloaded * 100 / total)))
                progress.setLabelText(f"Pobieranie aktualizacji... {downloaded / 1024 / 1024:.1f} MB")
            else:
                progress.setRange(0, 0)
                progress.setLabelText(f"Pobieranie aktualizacji... {downloaded / 1024 / 1024:.1f} MB")
            QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            downloaded_path = checker.download_update(path, update_progress)
        except UpdateDownloadCancelled:
            return
        except UpdateDownloadError as exc:
            QMessageBox.warning(self, "Aktualizacja Planory", str(exc))
            return
        finally:
            progress.close()

        if install_supported:
            info = checker.get_update_info() or {}
            try:
                launch_update_installer(downloaded_path, str(info.get("latest_version", "")))
            except UpdateInstallError as exc:
                QMessageBox.warning(self, "Aktualizacja Planory", str(exc))
                return
            self.hide()
            QApplication.closeAllWindows()
            QApplication.exit(0)
        else:
            QMessageBox.information(
                self,
                "Aktualizacja pobrana",
                f"Zapisano aktualizację w:\n{downloaded_path}\n\n"
                "Automatyczna instalacja jest dostępna w gotowej wersji Planory dla Windows i macOS.",
            )

    def _show_update_result(self, result: dict):
        if result.get("success"):
            QMessageBox.information(self, "Aktualizacja zakończona", str(result.get("message", "")))
        else:
            QMessageBox.warning(self, "Aktualizacja nieudana", str(result.get("message", "")))
