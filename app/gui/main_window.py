import copy
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QProgressDialog

from app.config import APP_ICON, AUTOSAVE_FILE, PROJECTS_DIR, UPDATE_DIR, UPDATE_URL
from app.core.app_info import APP_NAME, APP_VERSION
from app.core.group_tools import latest_group_leaders
from app.core.group_plan_store import GroupPlanStore
from app.core.people_roles import ASSIGNMENT_OPTIONS, eligible_people
from app.core.project_archive import ProjectArchive
from app.core.project_history import ProjectHistory
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
    can_install_automatically,
    consume_update_result,
    is_install_supported,
    launch_update_installer,
)
from app.gui.home_screen import HomeScreen
from app.gui.guide_dialog import GuideDialog
from app.gui.people_dialog import PeopleDialog
from app.gui.project_center_dialog import ProjectCenterDialog
from app.gui.project_selection_dialog import ProjectSelectionDialog
from app.gui.project_transfer_dialog import ProjectTransferDialog
from app.gui.schedule_type_screen import ScheduleTypeScreen
from app.gui.settings_dialog import SettingsDialog
from app.gui.animated_stack import AnimatedStackedWidget
from app.gui.responsive import fit_window_to_screen
from app.gui.theme_manager import build_stylesheet, responsive_scale_for_size
from app.gui.ui_feedback import UiFeedback
from app.gui.tutorial import (
    TutorialOverlay,
    TutorialStep,
    editor_tutorial_steps,
    find_tutorial_anchor,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ProjectIO.ensure_user_data()
        self.group_plan_store = GroupPlanStore()
        self.group_plan_store.migrate_from_archive(ProjectArchive().load_entries())
        self.project_history = ProjectHistory()
        self.people = ProjectIO.load_people()
        self.people_profiles = ProjectIO.load_people_profiles(self.people)
        self.settings = ProjectIO.load_settings()
        self.editor = None
        self._startup_update_scheduled = False
        self._recovery_checked = False
        self._home_tutorial_scheduled = False
        self._pending_update_result = consume_update_result()
        self._last_style_signature = None
        self._tutorial_overlay = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        fit_window_to_screen(self, 1360, 840, 540, 420)
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
            self.open_project_center,
            self.open_project_transfer,
            self.start_home_tutorial,
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
        self.history_timer = QTimer(self)
        self.history_timer.setInterval(1_500)
        self.history_timer.timeout.connect(self.observe_project_history)
        self.history_timer.start()
        self.responsive_style_timer = QTimer(self)
        self.responsive_style_timer.setSingleShot(True)
        self.responsive_style_timer.setInterval(80)
        self.responsive_style_timer.timeout.connect(self._apply_style)
        self._create_edit_actions()

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
        if (
            self.settings.get("tutorials_enabled", True)
            and not self._tutorial_seen("home")
            and not self._home_tutorial_scheduled
        ):
            self._home_tutorial_scheduled = True
            QTimer.singleShot(1600, self.start_home_tutorial)

    def _apply_style(self):
        app = QApplication.instance()
        styled_settings = dict(self.settings)
        styled_settings["responsive_scale"] = responsive_scale_for_size(self.width(), self.height())
        signature = (
            styled_settings.get("theme"),
            styled_settings.get("font_scale"),
            styled_settings.get("interface_density"),
            styled_settings.get("corner_style"),
            styled_settings["responsive_scale"],
        )
        if signature == self._last_style_signature:
            return
        self._last_style_signature = signature
        app.setProperty("animationSpeed", self.settings.get("animation_speed", 100))
        app.setProperty("responsiveScale", styled_settings["responsive_scale"])
        app.setStyleSheet(build_stylesheet(styled_settings))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "responsive_style_timer"):
            self.responsive_style_timer.start()

    def show_home(self):
        self.archive_current_project()
        self.refresh_home_summary()
        self.stack.setCurrentWidgetAnimated(self.home)
        QTimer.singleShot(0, self._sync_history_actions)

    def refresh_home_summary(self):
        self.home.set_duty_summary(
            "Otwórz Centrum projektów i wybierz zapisane grafiki, które mają zostać sprawdzone. "
            "Kopie awaryjne nie są uwzględniane w podsumowaniu."
        )

    def show_schedule_types(self):
        self.stack.setCurrentWidgetAnimated(self.schedule_types)
        QTimer.singleShot(0, self._sync_history_actions)

    def create_project(self, template_id: str):
        template = TemplateRegistry.get(template_id)
        if template:
            project = self.group_plan_store.load() if template_id == "field_service_groups" else None
            self.open_editor(
                template,
                copy.deepcopy(project or template.default_project),
                offer_tutorial=True,
            )

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Otwórz projekt",
            str(PROJECTS_DIR),
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

    def open_editor(
        self,
        template,
        project: dict,
        path: Path | None = None,
        reset_history: bool = True,
        offer_tutorial: bool = False,
    ):
        self.archive_current_project()
        if self.editor is not None:
            self.stack.removeWidget(self.editor)
            self.editor.deleteLater()
        if reset_history:
            self.project_history.reset(project)
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
        self.editor.wizard.tutorial_requested.connect(
            lambda template_id=template.id: self.start_editor_tutorial(template_id)
        )
        self._apply_role_filters(template.id)
        if template.id == "field_service_groups":
            self.group_plan_store.save(self.editor.project)
            self.editor.project_changed.connect(self.save_permanent_group_plan)
        if template.id == "cleaning_attendants":
            group_project = self.group_plan_store.load()
            leaders, group_names = latest_group_leaders(
                [{"project": group_project}] if group_project else []
            )
            self.editor.set_group_leaders(leaders, group_names)
        self.stack.setCurrentWidgetAnimated(self.editor)
        self._sync_history_actions()
        tutorial_id = f"editor:{template.id}"
        if (
            offer_tutorial
            and self.settings.get("tutorials_enabled", True)
            and not self._tutorial_seen(tutorial_id)
        ):
            QTimer.singleShot(550, lambda: self.start_editor_tutorial(template.id))

    def _tutorial_seen(self, tutorial_id: str) -> bool:
        return tutorial_id in self.settings.get("tutorials_completed", [])

    def _remember_tutorial(self, tutorial_id: str):
        completed = list(self.settings.get("tutorials_completed", []))
        if tutorial_id not in completed:
            completed.append(tutorial_id)
            self.settings["tutorials_completed"] = completed
            ProjectIO.save_settings(self.settings)

    def _show_tutorial(self, tutorial_id: str, title: str, steps: list[TutorialStep]):
        if self._tutorial_overlay is not None:
            try:
                self._tutorial_overlay.finish(False)
            except RuntimeError:
                pass
        if not steps:
            return
        overlay = TutorialOverlay(self, title, steps)
        self._tutorial_overlay = overlay

        def closed(_completed):
            self._remember_tutorial(tutorial_id)
            if self._tutorial_overlay is overlay:
                self._tutorial_overlay = None

        overlay.closed.connect(closed)
        overlay.start()

    def start_home_tutorial(self):
        if self.stack.currentWidget() is not self.home:
            self.show_home()
        steps = [
            TutorialStep(
                "Witaj w Planorze",
                "Ten samouczek przeprowadzi Cię przez główne bloki aplikacji. Podświetlenie trzyma się całych kart, "
                "więc działa też w trybie okienkowym i na mniejszych monitorach.",
                target=lambda: find_tutorial_anchor(self.home, "home_create"),
            ),
            TutorialStep(
                "Utwórz pierwszy grafik",
                "W tym bloku zaczynasz pracę. Kliknij „Utwórz nowy grafik”, wybierz generator, a potem przechodź "
                "krokami: dane, program lub osoby, podgląd i eksport.",
                target=lambda: find_tutorial_anchor(self.home, "home_create"),
            ),
            TutorialStep(
                "Biblioteka osób i role",
                "Tutaj dodajesz osoby, role oraz uprawnienia do konkretnych przydziałów. Generatory korzystają z tej "
                "listy do podpowiadania właściwych osób, ale w razie potrzeby można wpisać kogoś ręcznie.",
                target=lambda: find_tutorial_anchor(self.home, "home_people"),
            ),
            TutorialStep(
                "Import i eksport projektów",
                "Ten blok służy do przenoszenia edytowalnych grafików między komputerami. To nie jest eksport PDF, "
                "tylko kopia projektu, którą można później dalej poprawiać.",
                target=lambda: find_tutorial_anchor(self.home, "home_transfer"),
            ),
            TutorialStep(
                "Centrum projektów",
                "W centrum wybierasz zapisane grafiki do wspólnej analizy. Tam sprawdzisz nadchodzące obowiązki, "
                "statystyki, globalne kolizje i drukowanie zbiorcze.",
                target=lambda: find_tutorial_anchor(self.home, "home_center"),
            ),
            TutorialStep(
                "Aktualizacje",
                "Tutaj sprawdzisz, czy jest nowsza wersja Planory. Jeśli automatyczna instalacja nie ma uprawnień, "
                "aplikacja pozwoli pobrać gotowy plik EXE ręcznie.",
                target=lambda: find_tutorial_anchor(self.home, "home_updates"),
            ),
            TutorialStep(
                "Poradnik i dokumentacja",
                "Poradnik jest krótszą pomocą w aplikacji, a dokumentacja online opisuje funkcje dokładniej. "
                "Warto zajrzeć tam przy imporcie programu z JW albo przy pracy z kilkoma grafikami.",
                target=lambda: find_tutorial_anchor(self.home, "home_guide"),
            ),
            TutorialStep(
                "Ustawienia i ponowny samouczek",
                "W ustawieniach zmienisz motyw, skalę interfejsu, dźwięki, drukowanie oraz uruchomisz ten samouczek "
                "ponownie. Każdy generator ma też własny przycisk „Samouczek” w dolnym pasku kroków.",
                target=lambda: find_tutorial_anchor(self.home, "home_settings"),
            ),
        ]
        self._show_tutorial("home", "Pierwsze uruchomienie", steps)

    def start_editor_tutorial(self, template_id: str):
        if self.editor is None or self.editor.project.get("template_id") != template_id:
            return
        template = TemplateRegistry.get(template_id)
        if template:
            self._show_tutorial(
                f"editor:{template_id}",
                template.name,
                editor_tutorial_steps(template_id, self.editor),
            )

    def edit_people(self):
        dialog = PeopleDialog(self.people, self.people_profiles, self)
        if dialog.exec():
            self.people = dialog.people
            self.people_profiles = dialog.profiles
            ProjectIO.save_people_library(self.people, self.people_profiles)
            if self.editor is not None:
                template = TemplateRegistry.for_project(self.editor.project)
                self.editor.set_people(self.people)
                if template:
                    self._apply_role_filters(template.id)

    def _apply_role_filters(self, template_id: str):
        if self.editor is None:
            return

        def apply(combo, role):
            if combo is None:
                return
            current = combo.currentText()
            allowed = eligible_people(self.people, self.people_profiles, role)
            combo.blockSignals(True)
            combo.setEditable(True)
            combo.clear()
            combo.addItem("")
            combo.addItems(allowed)
            combo.setCurrentText(current)
            combo.setToolTip(
                f"Lista podpowiada osoby pasujące do przydziału: {ASSIGNMENT_OPTIONS[role]}. "
                "W wyjątkowej sytuacji możesz wpisać inną osobę ręcznie."
            )
            combo.blockSignals(False)

        if template_id == "cleaning_attendants":
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
            apply(self.editor.opening_prayer, "prayer")
            apply(self.editor.closing_prayer, "prayer")
            self.editor.set_role_people(
                {
                    role: eligible_people(self.people, self.people_profiles, role)
                    for role in ASSIGNMENT_OPTIONS
                }
            )
        elif template_id == "service_meetings":
            apply(self.editor.conductor, "service_conductor")

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings.update(dialog.values())
            ProjectIO.save_settings(self.settings)
            self._apply_style()
            if getattr(dialog, "start_tutorial_requested", False):
                QTimer.singleShot(250, self.start_home_tutorial)

    def open_guide(self):
        GuideDialog(self).exec()

    def open_project_transfer(self):
        ProjectTransferDialog(self).exec()

    def open_project_center(self):
        entries = self.select_analysis_projects("otwarcia Centrum projektów")
        if entries is None:
            return
        ProjectCenterDialog(
            entries,
            self.people,
            self.open_generated_project,
            self,
        ).exec()

    def select_analysis_projects(self, purpose: str) -> list[dict] | None:
        path = self.editor.project_path if self.editor is not None else None
        dialog = ProjectSelectionDialog(purpose, self.current_project(), path, self)
        if dialog.exec() != ProjectSelectionDialog.Accepted:
            return None
        return dialog.selected_entries()

    def current_project(self):
        return self.editor.project if self.editor is not None else None

    def open_generated_project(self, project, path=None):
        template = TemplateRegistry.for_project(project)
        if template:
            self.open_editor(template, project, Path(path) if path else None)

    def refresh_editor_after_tools(self):
        if self.editor is None:
            return
        project = self.editor.project
        path = self.editor.project_path
        template = TemplateRegistry.for_project(project)
        if template:
            self.project_history.observe(project)
            self.open_editor(template, project, path, reset_history=False)

    def _create_edit_actions(self):
        menu = self.menuBar().addMenu("Edycja")
        self.undo_action = QAction("Cofnij", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo_project)
        self.redo_action = QAction("Ponów", self)
        self.redo_action.setShortcuts((QKeySequence.Redo, QKeySequence("Ctrl+Y")))
        self.redo_action.triggered.connect(self.redo_project)
        menu.addAction(self.undo_action)
        menu.addAction(self.redo_action)
        self._sync_history_actions()

    def observe_project_history(self):
        project = self.current_project()
        if project:
            self.project_history.observe(project)
        self._sync_history_actions()

    def _sync_history_actions(self):
        if not hasattr(self, "undo_action"):
            return
        active = self.editor is not None and self.stack.currentWidget() is self.editor
        self.undo_action.setEnabled(active and self.project_history.can_undo())
        self.redo_action.setEnabled(active and self.project_history.can_redo())

    def undo_project(self):
        project = self.current_project()
        if not project or self.editor is None:
            return
        restored = self.project_history.undo(project)
        if restored is not None:
            template = TemplateRegistry.for_project(restored)
            path = self.editor.project_path
            if template:
                self.open_editor(template, restored, path, reset_history=False)
        self._sync_history_actions()

    def redo_project(self):
        if self.editor is None:
            return
        restored = self.project_history.redo()
        if restored is not None:
            template = TemplateRegistry.for_project(restored)
            path = self.editor.project_path
            if template:
                self.open_editor(template, restored, path, reset_history=False)
        self._sync_history_actions()

    def archive_current_project(self):
        project = self.current_project()
        if project and project.get("template_id") == "field_service_groups":
            try:
                self.group_plan_store.save(project)
            except OSError:
                pass

    def save_permanent_group_plan(self):
        project = self.current_project()
        if project and project.get("template_id") == "field_service_groups":
            try:
                self.group_plan_store.save(project)
            except OSError:
                pass

    def autosave_project(self):
        project = self.current_project()
        if project:
            try:
                ProjectIO.save_project(AUTOSAVE_FILE, project)
                if project.get("template_id") == "field_service_groups":
                    self.group_plan_store.save(project)
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
        self.archive_current_project()
        AUTOSAVE_FILE.unlink(missing_ok=True)
        super().closeEvent(event)

    def _legacy_check_updates_unused(self, quiet_if_current: bool = False):
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

    def _legacy_download_update_unused(self, checker: UpdateChecker):
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
        auto_install = can_install_automatically()
        install_possible = is_install_supported()
        message = QMessageBox(self)
        message.setWindowTitle("Dostępna aktualizacja")
        message.setIcon(QMessageBox.Information)
        message.setText(f"Dostępna jest wersja {info.get('latest_version')}.")
        details = f"Data wydania: {info.get('release_date', 'brak')}\n\n{notes_text}"
        if auto_install:
            details += (
                "\n\nPlanora zostanie zamknięta, zaktualizowana i uruchomiona ponownie. "
                "Przed kontynuowaniem zapisz otwarty projekt."
            )
        elif install_possible:
            details += (
                "\n\nNie wygląda na to, żeby Planora mogła sama podmienić plik programu w obecnym folderze. "
                "Możesz pobrać gotowy EXE i uruchomić go ręcznie."
            )
        else:
            details += "\n\nW tym uruchomieniu dostępne jest ręczne pobranie pliku aktualizacji."
        message.setInformativeText(details)

        auto_button = None
        if auto_install:
            auto_button = message.addButton("Pobierz i zainstaluj", QMessageBox.AcceptRole)
        manual_button = message.addButton("Pobierz EXE ręcznie", QMessageBox.ActionRole)
        message.addButton(QMessageBox.Close)
        message.exec()
        if auto_button is not None and message.clickedButton() is auto_button:
            self.download_update(checker, install_automatically=True)
        elif message.clickedButton() is manual_button:
            self.download_update(checker, install_automatically=False, force_manual=True)

    def download_update(
        self,
        checker: UpdateChecker,
        install_automatically: bool | None = None,
        force_manual: bool = False,
    ):
        install_automatically = can_install_automatically() if install_automatically is None else install_automatically
        manual_url = checker.get_manual_download_url()
        use_manual_file = force_manual or (not install_automatically and bool(manual_url))
        download_url = manual_url if use_manual_file else None

        if install_automatically:
            UPDATE_DIR.mkdir(parents=True, exist_ok=True)
            path = UPDATE_DIR / checker.suggested_filename()
        else:
            filename = checker.suggested_manual_filename() if use_manual_file else checker.suggested_filename()
            default_path = Path.home() / "Downloads" / filename
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Zapisz aktualizację Planory",
                str(default_path),
                "Aplikacja EXE (*.exe);;Archiwum ZIP (*.zip);;Wszystkie pliki (*)",
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
            downloaded_path = checker.download_update(path, update_progress, url=download_url)
        except UpdateDownloadCancelled:
            return
        except UpdateDownloadError as exc:
            QMessageBox.warning(self, "Aktualizacja Planory", str(exc))
            return
        finally:
            progress.close()

        if install_automatically:
            info = checker.get_update_info() or {}
            try:
                launch_update_installer(downloaded_path, str(info.get("latest_version", "")))
            except UpdateInstallError as exc:
                QMessageBox.warning(
                    self,
                    "Aktualizacja Planory",
                    f"{exc}\n\nPaczka została pobrana tutaj:\n{downloaded_path}",
                )
                return
            self.hide()
            QApplication.closeAllWindows()
            QApplication.exit(0)
        else:
            QMessageBox.information(
                self,
                "Aktualizacja pobrana",
                f"Zapisano aktualizację w:\n{downloaded_path}\n\n"
                "Jeśli pobrałeś plik EXE, zamknij starą Planorę i uruchom pobrany plik.",
            )

    def _show_update_result(self, result: dict):
        if result.get("success"):
            QMessageBox.information(self, "Aktualizacja zakończona", str(result.get("message", "")))
        else:
            QMessageBox.warning(self, "Aktualizacja nieudana", str(result.get("message", "")))
