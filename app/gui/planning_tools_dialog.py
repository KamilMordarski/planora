from collections import defaultdict
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.assignment_tools import (
    assigned_people_by_date,
    build_service_meetings_plan,
    export_ics,
    export_person_assignments,
    generate_recurring_dates,
    shift_project_dates,
)
from app.core.people_roles import eligible_people
from app.core.template_registry import TemplateRegistry
from app.gui.responsive import configure_form


class PlanningToolsDialog(QDialog):
    def __init__(self, people, profiles, current_project, create_project, project_changed, archived_projects=None, parent=None):
        super().__init__(parent)
        self.people = list(people)
        self.profiles = dict(profiles)
        self.current_project = current_project
        self.create_project = create_project
        self.project_changed = project_changed
        self.archived_projects = archived_projects
        self.setWindowTitle("Asystent i narzędzia planowania")
        self.resize(900, 720)

        root = QVBoxLayout(self)
        title = QLabel("Asystent układania grafików")
        title.setObjectName("screenTitle")
        subtitle = QLabel(
            "Generuj terminy, przydzielaj osoby zgodnie z rolami, edytuj wiele dat i eksportuj obowiązki do kalendarza."
        )
        subtitle.setObjectName("screenSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._assistant_tab(), "Asystent")
        tabs.addTab(self._bulk_tab(), "Masowa edycja")
        tabs.addTab(self._export_tab(), "Kalendarz i przydziały")
        root.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _date_controls(self):
        widget = QWidget()
        form = configure_form(QFormLayout(widget))
        start = QDateEdit(QDate.currentDate())
        end = QDateEdit(QDate.currentDate().addMonths(1))
        for field in (start, end):
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd.MM.yyyy")
        weekdays = {}
        weekday_row = QHBoxLayout()
        for number, label in enumerate(("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Niedz")):
            check = QCheckBox(label)
            check.setChecked(number in (2, 5, 6))
            weekdays[number] = check
            weekday_row.addWidget(check)
        form.addRow("Od:", start)
        form.addRow("Do:", end)
        form.addRow("Dni tygodnia:", weekday_row)
        return widget, start, end, weekdays

    @staticmethod
    def _python_date(field):
        value = field.date()
        return date(value.year(), value.month(), value.day())

    def _selected_dates(self, start, end, weekdays):
        selected = {number for number, check in weekdays.items() if check.isChecked()}
        return generate_recurring_dates(self._python_date(start), self._python_date(end), selected)

    def _assistant_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QGroupBox("Nowy plan zbiórek do służby")
        info_layout = QVBoxLayout(info)
        eligible = eligible_people(self.people, self.profiles, "service_conductor")
        eligibility = QLabel(
            f"Osoby z rolą „Prowadzenie zbiórki do służby”: {len(eligible)}. "
            "Asystent rozdziela obowiązki możliwie równo i unika tej samej osoby dwa razy z rzędu."
        )
        eligibility.setObjectName("helpText")
        eligibility.setWordWrap(True)
        info_layout.addWidget(eligibility)
        self.assistant_people = QListWidget()
        self.assistant_people.setMinimumHeight(130)
        for person in eligible:
            item = QListWidgetItem(person)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.assistant_people.addItem(item)
        info_layout.addWidget(QLabel("Osoby dostępne w tym planie:"))
        info_layout.addWidget(self.assistant_people)
        controls, self.assistant_start, self.assistant_end, self.assistant_weekdays = self._date_controls()
        info_layout.addWidget(controls)
        form = configure_form(QFormLayout())
        self.assistant_time = QLineEdit("17:15")
        self.assistant_place = QLineEdit("Sala Królestwa")
        self.balance_assignments = QCheckBox("Rozdzielaj obowiązki możliwie równo")
        self.balance_assignments.setChecked(True)
        self.avoid_consecutive = QCheckBox("Unikaj tej samej osoby dwa razy z rzędu")
        self.avoid_consecutive.setChecked(True)
        form.addRow("Domyślna godzina:", self.assistant_time)
        form.addRow("Domyślne miejsce:", self.assistant_place)
        form.addRow("Zasady:", self.balance_assignments)
        form.addRow("", self.avoid_consecutive)
        info_layout.addLayout(form)
        generate = QPushButton("Utwórz i otwórz propozycję")
        generate.setObjectName("primaryButton")
        generate.clicked.connect(self.generate_plan)
        info_layout.addWidget(generate)
        layout.addWidget(info)
        layout.addStretch()
        return tab

    def _bulk_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        current = QGroupBox("Aktualnie otwarty projekt")
        current_layout = QVBoxLayout(current)
        self.project_status = QLabel()
        self.project_status.setObjectName("helpText")
        self.project_status.setWordWrap(True)
        current_layout.addWidget(self.project_status)
        self.bulk_meetings = QListWidget()
        self.bulk_meetings.setMinimumHeight(150)
        current_layout.addWidget(self.bulk_meetings)
        selection_row = QHBoxLayout()
        select_all = QPushButton("Zaznacz wszystkie terminy")
        select_none = QPushButton("Wyczyść zaznaczenie")
        select_all.clicked.connect(lambda: self._set_bulk_checks(Qt.Checked))
        select_none.clicked.connect(lambda: self._set_bulk_checks(Qt.Unchecked))
        selection_row.addWidget(select_all)
        selection_row.addWidget(select_none)
        current_layout.addLayout(selection_row)

        shift_form = configure_form(QFormLayout())
        self.shift_days = QSpinBox()
        self.shift_days.setRange(-365, 365)
        self.shift_days.setValue(7)
        shift_button = QPushButton("Przesuń zaznaczone daty")
        shift_button.clicked.connect(self.shift_dates)
        shift_form.addRow("Przesunięcie w dniach:", self.shift_days)
        shift_form.addRow("", shift_button)
        current_layout.addLayout(shift_form)

        service_group = QGroupBox("Zbiórki do służby")
        service_form = configure_form(QFormLayout(service_group))
        controls, self.bulk_start, self.bulk_end, self.bulk_weekdays = self._date_controls()
        self.bulk_time = QLineEdit()
        self.bulk_place = QLineEdit()
        append_dates = QPushButton("Dodaj wygenerowane terminy do projektu")
        append_dates.clicked.connect(self.append_dates)
        apply_common = QPushButton("Ustaw godzinę i miejsce w zaznaczonych zbiórkach")
        apply_common.clicked.connect(self.apply_common_values)
        service_form.addRow(controls)
        service_form.addRow("Wspólna godzina:", self.bulk_time)
        service_form.addRow("Wspólne miejsce:", self.bulk_place)
        service_form.addRow("", append_dates)
        service_form.addRow("", apply_common)
        current_layout.addWidget(service_group)
        layout.addWidget(current)
        layout.addStretch()
        self._refresh_project_status()
        return tab

    def _export_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("Eksport obowiązków z otwartego projektu")
        form = configure_form(QFormLayout(group))
        self.export_person = QComboBox()
        self.export_person.addItem("Wszyscy", "")
        for person in self.people:
            self.export_person.addItem(person, person)
        calendar = QPushButton("Eksportuj kalendarz .ics")
        calendar.setToolTip("Plik ICS można zaimportować do Google Calendar, Outlooka i Kalendarza Apple.")
        calendar.clicked.connect(self.export_calendar)
        person_file = QPushButton("Eksportuj przydziały osoby do TXT")
        person_file.clicked.connect(self.export_person_file)
        form.addRow("Osoba:", self.export_person)
        form.addRow("", calendar)
        form.addRow("", person_file)
        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _project(self):
        return self.current_project() if callable(self.current_project) else None

    def _refresh_project_status(self):
        project = self._project()
        self.bulk_meetings.clear()
        if project:
            template = TemplateRegistry.for_project(project)
            self.project_status.setText(f"Otwarty projekt: {template.name if template else project.get('template_id', '')}")
            if project.get("template_id") == "service_meetings":
                for row in project.get("meetings", []):
                    label = " · ".join(filter(None, (row.get("date"), row.get("time"), row.get("place")))) or "Bez daty"
                    item = QListWidgetItem(label)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self.bulk_meetings.addItem(item)
                self.bulk_meetings.setEnabled(True)
            else:
                item = QListWidgetItem("Ten typ projektu obsługuje przesunięcie wszystkich rozpoznanych dat.")
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                self.bulk_meetings.addItem(item)
                self.bulk_meetings.setEnabled(False)
        else:
            self.project_status.setText("Najpierw otwórz projekt, aby użyć masowej edycji lub eksportu.")
            self.bulk_meetings.setEnabled(False)

    def _set_bulk_checks(self, state):
        for index in range(self.bulk_meetings.count()):
            self.bulk_meetings.item(index).setCheckState(state)

    def _selected_meeting_indices(self):
        return [
            index
            for index in range(self.bulk_meetings.count())
            if self.bulk_meetings.item(index).checkState() == Qt.Checked
        ]

    def _assistant_selected_people(self):
        return [
            self.assistant_people.item(index).text()
            for index in range(self.assistant_people.count())
            if self.assistant_people.item(index).checkState() == Qt.Checked
        ]

    def generate_plan(self):
        dates = self._selected_dates(self.assistant_start, self.assistant_end, self.assistant_weekdays)
        project = TemplateRegistry.get("service_meetings").default_project
        blocked = defaultdict(set)
        for entry in self.archived_projects() if callable(self.archived_projects) else []:
            for date_value, people in assigned_people_by_date(entry.get("project")).items():
                blocked[date_value].update(people)
        for date_value, people in assigned_people_by_date(self._project()).items():
            blocked[date_value].update(people)
        project["meetings"] = build_service_meetings_plan(
            project,
            dates,
            self._assistant_selected_people(),
            self.profiles,
            self.assistant_time.text(),
            self.assistant_place.text(),
            self.balance_assignments.isChecked(),
            self.avoid_consecutive.isChecked(),
            dict(blocked),
        )
        if dates and not project["meetings"]:
            QMessageBox.warning(self, "Brak uprawnionych osób", "Przypisz przynajmniej jednej osobie rolę prowadzenia zbiórki.")
            return
        missing = sum(not row.get("conductor") for row in project["meetings"])
        if missing:
            QMessageBox.information(
                self,
                "Terminy wymagające decyzji",
                f"Pozostawiono bez prowadzącego: {missing}. W tych dniach wszystkie dostępne osoby mają już obowiązek "
                "w ostatnio edytowanych projektach.",
            )
        self.create_project(project)
        self.accept()

    def shift_dates(self):
        project = self._project()
        if not project:
            return
        if project.get("template_id") == "service_meetings":
            selected = self._selected_meeting_indices()
            if not selected:
                QMessageBox.warning(self, "Wybierz terminy", "Zaznacz terminy, które mają zostać przesunięte.")
                return
            subset = {"template_id": "service_meetings", "meetings": [project["meetings"][index] for index in selected]}
            changed = shift_project_dates(subset, self.shift_days.value())
        else:
            changed = shift_project_dates(project, self.shift_days.value())
        self.project_changed()
        self._refresh_project_status()
        QMessageBox.information(self, "Masowa edycja", f"Przesunięto daty w polach: {changed}.")

    def append_dates(self):
        project = self._project()
        if not project or project.get("template_id") != "service_meetings":
            QMessageBox.warning(self, "Nieobsługiwany projekt", "Ta operacja wymaga otwartego projektu „Zbiórki do służby”.")
            return
        dates = self._selected_dates(self.bulk_start, self.bulk_end, self.bulk_weekdays)
        project["meetings"].extend(
            build_service_meetings_plan(
                project,
                dates,
                self.people,
                self.profiles,
                self.bulk_time.text(),
                self.bulk_place.text(),
            )
        )
        self.project_changed()
        self._refresh_project_status()

    def apply_common_values(self):
        project = self._project()
        if not project or project.get("template_id") != "service_meetings":
            return
        selected = self._selected_meeting_indices()
        if not selected:
            QMessageBox.warning(self, "Wybierz terminy", "Zaznacz terminy, które chcesz zmienić.")
            return
        for index in selected:
            row = project["meetings"][index]
            if self.bulk_time.text():
                row["time"] = self.bulk_time.text()
            if self.bulk_place.text():
                row["place"] = self.bulk_place.text()
        self.project_changed()
        self._refresh_project_status()

    def export_calendar(self):
        project = self._project()
        if not project:
            return
        person = self.export_person.currentData()
        path, _ = QFileDialog.getSaveFileName(self, "Eksportuj kalendarz", str(USER_DATA_DIR / "planora.ics"), "Kalendarz (*.ics)")
        if path:
            export_ics(Path(path), project, person)
            QMessageBox.information(self, "Gotowe", "Plik kalendarza został zapisany.")

    def export_person_file(self):
        project = self._project()
        person = self.export_person.currentData()
        if not project or not person:
            QMessageBox.warning(self, "Wybierz osobę", "Wybierz konkretną osobę z listy.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Eksportuj przydziały osoby", str(USER_DATA_DIR / f"przydzialy-{person}.txt"), "Tekst (*.txt)"
        )
        if path:
            export_person_assignments(Path(path), project, person)
            QMessageBox.information(self, "Gotowe", "Lista przydziałów została zapisana.")
