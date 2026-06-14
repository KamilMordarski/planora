from collections import Counter, defaultdict
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.assignment_tools import (
    archive_assignments,
    assignment_rows_for_person,
    export_assignment_rows_ics,
    export_assignment_rows_text,
    parse_date,
)
from app.core.project_archive import ProjectArchive, RETENTION_DAYS


def _table(headers: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class ProjectCenterDialog(QDialog):
    def __init__(self, archive: ProjectArchive, people: list[str], open_project, parent=None):
        super().__init__(parent)
        self.archive = archive
        self.people = list(people)
        self.open_project = open_project
        self.entries = []
        self.assignments = []
        self._marked_dates = set()
        self.setWindowTitle("Centrum projektów")
        self.resize(1120, 780)

        root = QVBoxLayout(self)
        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_text = QVBoxLayout()
        title = QLabel("Centrum projektów")
        title.setObjectName("screenTitle")
        self.summary = QLabel()
        self.summary.setObjectName("screenSubtitle")
        self.summary.setWordWrap(True)
        hero_text.addWidget(title)
        hero_text.addWidget(self.summary)
        refresh = QPushButton("Odśwież dane")
        refresh.clicked.connect(self.reload)
        hero_layout.addLayout(hero_text, 1)
        hero_layout.addWidget(refresh)
        root.addWidget(hero)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._calendar_tab(), "Centralny kalendarz")
        self.tabs.addTab(self._statistics_tab(), "Statystyki i równy podział")
        self.tabs.addTab(self._person_tab(), "Indywidualny plan osoby")
        root.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.reload()

    def _calendar_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel("Wybierz dzień, aby zobaczyć obowiązki ze wszystkich automatycznie zapisanych projektów.")
        info.setObjectName("helpText")
        info.setWordWrap(True)
        layout.addWidget(info)
        splitter = QSplitter()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._refresh_calendar_rows)
        splitter.addWidget(self.calendar)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.day_heading = QLabel()
        self.day_heading.setObjectName("cardTitle")
        self.calendar_table = _table(("Projekt", "Osoba", "Obowiązek", "Szczegóły"))
        self.calendar_table.doubleClicked.connect(self._open_selected_calendar_project)
        open_button = QPushButton("Otwórz projekt wybranego obowiązku")
        open_button.clicked.connect(self._open_selected_calendar_project)
        right_layout.addWidget(self.day_heading)
        right_layout.addWidget(self.calendar_table, 1)
        right_layout.addWidget(open_button)
        splitter.addWidget(right)
        splitter.setSizes([400, 650])
        layout.addWidget(splitter, 1)
        return tab

    def _statistics_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.balance_summary = QLabel()
        self.balance_summary.setObjectName("screenSubtitle")
        self.balance_summary.setWordWrap(True)
        self.statistics_table = _table(("Osoba", "Łącznie", "Podział obowiązków"))
        layout.addWidget(self.balance_summary)
        layout.addWidget(self.statistics_table, 1)
        return tab

    def _person_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        row.addWidget(QLabel("Osoba:"))
        self.person_combo = QComboBox()
        self.person_combo.currentTextChanged.connect(self._refresh_person_rows)
        row.addWidget(self.person_combo, 1)
        export_text = QPushButton("Eksportuj TXT")
        export_calendar = QPushButton("Eksportuj ICS")
        export_text.clicked.connect(self._export_person_text)
        export_calendar.clicked.connect(self._export_person_calendar)
        row.addWidget(export_text)
        row.addWidget(export_calendar)
        self.person_summary = QLabel()
        self.person_summary.setObjectName("helpText")
        self.person_table = _table(("Data", "Projekt", "Obowiązek", "Szczegóły"))
        layout.addLayout(row)
        layout.addWidget(self.person_summary)
        layout.addWidget(self.person_table, 1)
        return tab

    def reload(self):
        self.archive.cleanup()
        self.entries = self.archive.load_entries()
        self.assignments = archive_assignments(self.entries)
        dated = sum(parse_date(item.get("date")) is not None for item in self.assignments)
        self.summary.setText(
            f"Planora przechowuje lokalnie {len(self.entries)} ostatnio edytowanych projektów i "
            f"{len(self.assignments)} przydziałów. Rozpoznane daty w kalendarzu: {dated}. "
            f"Archiwum jest automatycznie usuwane po {RETENTION_DAYS} dniach."
        )
        self._mark_calendar_dates()
        self._refresh_calendar_rows()
        self._refresh_statistics()
        self._refresh_people()

    def _mark_calendar_dates(self):
        clear_format = QTextCharFormat()
        for value in self._marked_dates:
            self.calendar.setDateTextFormat(value, clear_format)
        self._marked_dates = set()
        highlight = QTextCharFormat()
        highlight.setBackground(QColor("#dbe7ee"))
        highlight.setForeground(QColor("#1769aa"))
        highlight.setFontWeight(700)
        first_date = None
        for assignment in self.assignments:
            parsed = parse_date(assignment.get("date"))
            if not parsed:
                continue
            value = QDate(parsed.year, parsed.month, parsed.day)
            self.calendar.setDateTextFormat(value, highlight)
            self._marked_dates.add(value)
            first_date = first_date or value
        if first_date and not any(
            parse_date(item.get("date")) == self._selected_python_date() for item in self.assignments
        ):
            self.calendar.setSelectedDate(first_date)

    def _selected_python_date(self):
        selected = self.calendar.selectedDate()
        return selected.toPython()

    def _refresh_calendar_rows(self):
        selected = self._selected_python_date()
        rows = [item for item in self.assignments if parse_date(item.get("date")) == selected]
        counts = Counter(item.get("person", "").casefold() for item in rows)
        collisions = sum(count > 1 for count in counts.values())
        self.day_heading.setText(
            f"{selected.strftime('%d.%m.%Y')} · obowiązki: {len(rows)} · kolizje między projektami: {collisions}"
        )
        self.calendar_table.setRowCount(len(rows))
        for row_index, assignment in enumerate(rows):
            values = (
                assignment.get("project_title", ""),
                assignment.get("person", ""),
                assignment.get("role", ""),
                assignment.get("details", ""),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, assignment.get("archive_id", ""))
                if counts[assignment.get("person", "").casefold()] > 1:
                    item.setBackground(QColor("#f7d9d9"))
                self.calendar_table.setItem(row_index, column, item)

    def _refresh_statistics(self):
        names = sorted(set(self.people) | {item["person"] for item in self.assignments}, key=str.casefold)
        by_person = defaultdict(Counter)
        for item in self.assignments:
            by_person[item["person"]][item["role"]] += 1
        self.statistics_table.setRowCount(len(names))
        totals = []
        for row, person in enumerate(names):
            counts = by_person[person]
            total = sum(counts.values())
            totals.append((person, total))
            breakdown = ", ".join(f"{role}: {count}" for role, count in counts.most_common()) or "Brak przydziałów"
            for column, value in enumerate((person, total, breakdown)):
                self.statistics_table.setItem(row, column, QTableWidgetItem(str(value)))
        if totals:
            most = max(totals, key=lambda item: item[1])
            least = min(totals, key=lambda item: item[1])
            difference = most[1] - least[1]
            self.balance_summary.setText(
                f"Różnica między największą i najmniejszą liczbą przydziałów: {difference}. "
                f"Najwięcej: {most[0]} ({most[1]}), najmniej: {least[0]} ({least[1]})."
            )
        else:
            self.balance_summary.setText("Brak danych do obliczenia podziału obowiązków.")

    def _refresh_people(self):
        current = self.person_combo.currentText()
        names = sorted(set(self.people) | {item["person"] for item in self.assignments}, key=str.casefold)
        self.person_combo.blockSignals(True)
        self.person_combo.clear()
        self.person_combo.addItems(names)
        self.person_combo.setCurrentText(current if current in names else (names[0] if names else ""))
        self.person_combo.blockSignals(False)
        self._refresh_person_rows()

    def _person_rows(self) -> list[dict]:
        return assignment_rows_for_person(self.assignments, self.person_combo.currentText())

    def _refresh_person_rows(self):
        rows = sorted(self._person_rows(), key=lambda item: (item.get("date", ""), item.get("role", "")))
        self.person_summary.setText(f"Liczba przydziałów wybranej osoby: {len(rows)}")
        self.person_table.setRowCount(len(rows))
        for row_index, assignment in enumerate(rows):
            for column, value in enumerate(
                (
                    assignment.get("date", ""),
                    assignment.get("project_title", ""),
                    assignment.get("role", ""),
                    assignment.get("details", ""),
                )
            ):
                self.person_table.setItem(row_index, column, QTableWidgetItem(str(value)))

    def _open_selected_calendar_project(self):
        row = self.calendar_table.currentRow()
        if row < 0:
            return
        archive_id = self.calendar_table.item(row, 0).data(Qt.UserRole)
        entry = next((item for item in self.entries if item.get("archive_id") == archive_id), None)
        if entry:
            self.open_project(entry["project"])
            self.accept()

    def _export_person_text(self):
        person = self.person_combo.currentText()
        if not person:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Eksportuj indywidualny plan",
            str(USER_DATA_DIR / f"plan-{person}.txt"),
            "Tekst (*.txt)",
        )
        if path:
            export_assignment_rows_text(Path(path), self._person_rows(), person)
            QMessageBox.information(self, "Gotowe", "Indywidualny plan został zapisany.")

    def _export_person_calendar(self):
        person = self.person_combo.currentText()
        if not person:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Eksportuj indywidualny kalendarz",
            str(USER_DATA_DIR / f"plan-{person}.ics"),
            "Kalendarz (*.ics)",
        )
        if path:
            export_assignment_rows_ics(Path(path), self._person_rows())
            QMessageBox.information(self, "Gotowe", "Indywidualny kalendarz został zapisany.")
