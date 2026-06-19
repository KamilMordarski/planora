from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
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
    assignment_causes_collision,
    archive_assignments,
    assignment_rows_for_person,
    export_assignment_rows_ics,
    export_assignment_rows_text,
    format_assignment_message,
    global_assignment_collisions,
    parse_date,
    upcoming_assignments,
)
from app.core.project_archive import ProjectArchive
from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry
from app.gui.printing import print_pages
from app.gui.responsive import ResponsiveActionBar, fit_window_to_screen


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
    def __init__(self, entries: list[dict], people: list[str], open_project, parent=None):
        super().__init__(parent)
        self.entries = list(entries)
        self.people = list(people)
        self.open_project = open_project
        self.assignments = []
        self._marked_dates = set()
        self.setWindowTitle("Centrum projektów")
        fit_window_to_screen(self, 1120, 780, 500, 400)

        root = QVBoxLayout(self)
        hero = QFrame()
        hero.setObjectName("heroCard")
        self.hero_layout = QBoxLayout(QBoxLayout.LeftToRight, hero)
        hero_layout = self.hero_layout
        hero_text = QVBoxLayout()
        title = QLabel("Centrum projektów")
        title.setObjectName("screenTitle")
        self.summary = QLabel()
        self.summary.setObjectName("screenSubtitle")
        self.summary.setWordWrap(True)
        hero_text.addWidget(title)
        hero_text.addWidget(self.summary)
        refresh = QPushButton("Odśwież wybrane pliki")
        refresh.setToolTip("Ponownie odczytuje z dysku projekty wybrane przed otwarciem Centrum.")
        refresh.clicked.connect(self.reload_from_files)
        hero_layout.addLayout(hero_text, 1)
        hero_layout.addWidget(refresh)
        root.addWidget(hero)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._calendar_tab(), "Centralny kalendarz")
        self.tabs.addTab(self._upcoming_tab(), "Nadchodzące obowiązki")
        self.tabs.addTab(self._collisions_tab(), "Globalne kolizje")
        self.tabs.addTab(self._statistics_tab(), "Statystyki i równy podział")
        self.tabs.addTab(self._person_tab(), "Indywidualny plan osoby")
        self.tabs.addTab(self._batch_print_tab(), "Drukowanie zbiorcze")
        root.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.reload()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "hero_layout"):
            return
        compact = self.width() < 850
        self.hero_layout.setDirection(QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight)
        orientation = Qt.Vertical if compact else Qt.Horizontal
        if hasattr(self, "calendar_splitter") and self.calendar_splitter.orientation() != orientation:
            self.calendar_splitter.setOrientation(orientation)
            self.calendar_splitter.setSizes([320, 520] if compact else [400, 650])

    def _calendar_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel("Wybierz dzień, aby zobaczyć obowiązki z projektów wskazanych przed otwarciem Centrum.")
        info.setObjectName("helpText")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.calendar_splitter = QSplitter()
        splitter = self.calendar_splitter
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

    def _upcoming_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Pokaż obowiązki z najbliższych:"))
        self.upcoming_range = QComboBox()
        for label, days in (("7 dni", 7), ("14 dni", 14), ("30 dni", 30), ("90 dni", 90)):
            self.upcoming_range.addItem(label, days)
        self.upcoming_range.setCurrentIndex(2)
        self.upcoming_range.currentIndexChanged.connect(self._refresh_upcoming)
        controls.addWidget(self.upcoming_range)
        controls.addStretch()
        self.upcoming_summary = QLabel()
        self.upcoming_summary.setObjectName("helpText")
        self.upcoming_table = _table(("Data", "Osoba", "Obowiązek", "Projekt", "Szczegóły"))
        layout.addLayout(controls)
        layout.addWidget(self.upcoming_summary)
        layout.addWidget(self.upcoming_table, 1)
        return tab

    def _collisions_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(
            "Kolizja oznacza, że ta sama osoba ma co najmniej dwa obowiązki tego samego dnia "
            "w jednym lub kilku wybranych projektach. Sprzątanie sali, modlitwy i prowadzenie zbiórki "
            "nie są traktowane jako kolizje."
        )
        info.setObjectName("helpText")
        info.setWordWrap(True)
        self.collisions_summary = QLabel()
        self.collisions_summary.setObjectName("screenSubtitle")
        self.collisions_table = _table(("Data", "Osoba", "Liczba", "Obowiązki", "Projekty"))
        layout.addWidget(info)
        layout.addWidget(self.collisions_summary)
        layout.addWidget(self.collisions_table, 1)
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
        copy_message = QPushButton("Kopiuj wiadomość")
        send_email = QPushButton("Wyślij e-mailem")
        export_text.clicked.connect(self._export_person_text)
        export_calendar.clicked.connect(self._export_person_calendar)
        copy_message.clicked.connect(self._copy_person_message)
        send_email.clicked.connect(self._email_person_message)
        self.person_summary = QLabel()
        self.person_summary.setObjectName("helpText")
        self.person_table = _table(("Data", "Projekt", "Obowiązek", "Szczegóły"))
        layout.addLayout(row)
        layout.addWidget(ResponsiveActionBar([export_text, export_calendar, copy_message, send_email], 140, 4))
        layout.addWidget(self.person_summary)
        layout.addWidget(self.person_table, 1)
        return tab

    def _batch_print_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(
            "Zaznacz projekty, które mają zostać wysłane do drukarki jako jedno zadanie. "
            "Każdy projekt korzysta ze swojego aktualnego renderera."
        )
        info.setObjectName("helpText")
        info.setWordWrap(True)
        select_all = QPushButton("Zaznacz wszystko")
        select_none = QPushButton("Odznacz wszystko")
        print_selected = QPushButton("Drukuj zaznaczone")
        print_selected.setObjectName("primaryButton")
        select_all.clicked.connect(lambda: self._set_all_print_checks(Qt.Checked))
        select_none.clicked.connect(lambda: self._set_all_print_checks(Qt.Unchecked))
        print_selected.clicked.connect(self._print_selected_projects)
        self.batch_print_table = _table(("Drukuj", "Projekt", "Szablon", "Ostatnia zmiana"))
        layout.addWidget(info)
        layout.addWidget(ResponsiveActionBar([select_all, select_none, print_selected], 150, 3))
        layout.addWidget(self.batch_print_table, 1)
        return tab

    def reload(self):
        self.assignments = archive_assignments(self.entries)
        dated = sum(parse_date(item.get("date")) is not None for item in self.assignments)
        self.summary.setText(
            f"Wybrano {len(self.entries)} projektów i znaleziono {len(self.assignments)} przydziałów. "
            f"Rozpoznane daty w kalendarzu: {dated}. Kopie awaryjne nie są analizowane."
        )
        self._mark_calendar_dates()
        self._refresh_calendar_rows()
        self._refresh_statistics()
        self._refresh_people()
        self._refresh_upcoming()
        self._refresh_collisions()
        self._refresh_batch_print()

    def reload_from_files(self):
        refreshed = []
        updated = 0
        for entry in self.entries:
            source_path = str(entry.get("source_path", "")).strip()
            if source_path:
                try:
                    path = Path(source_path)
                    project = ProjectIO.load_project(path)
                    refreshed.append(ProjectArchive.entry_for_project(project, path))
                    updated += 1
                    continue
                except (OSError, ValueError):
                    pass
            refreshed.append(entry)
        self.entries = refreshed
        self.reload()
        self.summary.setText(self.summary.text() + f" Ponownie odczytano z dysku: {updated}.")

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
        counts = Counter(
            item.get("person", "").casefold()
            for item in rows
            if assignment_causes_collision(item)
        )
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
                if (
                    assignment_causes_collision(assignment)
                    and counts[assignment.get("person", "").casefold()] > 1
                ):
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

    def _refresh_upcoming(self):
        days = self.upcoming_range.currentData() or 30
        rows = upcoming_assignments(self.assignments, date.today(), days)
        self.upcoming_summary.setText(f"Znaleziono {len(rows)} obowiązków w ciągu najbliższych {days} dni.")
        self.upcoming_table.setRowCount(len(rows))
        for row_index, assignment in enumerate(rows):
            values = (
                assignment.get("date", ""),
                assignment.get("person", ""),
                assignment.get("role", ""),
                assignment.get("project_title", ""),
                assignment.get("details", ""),
            )
            for column, value in enumerate(values):
                self.upcoming_table.setItem(row_index, column, QTableWidgetItem(str(value)))

    def _refresh_collisions(self):
        collisions = global_assignment_collisions(self.assignments)
        self.collisions_summary.setText(
            "Brak wykrytych kolizji."
            if not collisions
            else f"Wykryto {len(collisions)} kolizji wymagających sprawdzenia."
        )
        self.collisions_table.setRowCount(len(collisions))
        for row_index, collision in enumerate(collisions):
            rows = collision["assignments"]
            values = (
                collision["date"],
                collision["person"],
                len(rows),
                "; ".join(item.get("role", "") for item in rows),
                "; ".join(dict.fromkeys(item.get("project_title", "") for item in rows)),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setBackground(QColor("#f7d9d9"))
                self.collisions_table.setItem(row_index, column, item)

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
            self.open_project(entry["project"], entry.get("source_path") or None)
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

    def _person_message(self) -> str:
        return format_assignment_message(
            upcoming_assignments(self._person_rows(), date.today(), 90),
            self.person_combo.currentText(),
        )

    def _copy_person_message(self):
        if not self.person_combo.currentText():
            return
        QApplication.clipboard().setText(self._person_message())
        QMessageBox.information(self, "Gotowe", "Wiadomość z przydziałami została skopiowana.")

    def _email_person_message(self):
        if not self.person_combo.currentText():
            return
        subject = quote(f"Przydziały — {self.person_combo.currentText()}")
        body = quote(self._person_message())
        QDesktopServices.openUrl(QUrl(f"mailto:?subject={subject}&body={body}"))

    def _refresh_batch_print(self):
        self.batch_print_table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Unchecked)
            check.setData(Qt.UserRole, entry.get("archive_id", ""))
            self.batch_print_table.setItem(row, 0, check)
            for column, value in enumerate(
                (
                    entry.get("title", ""),
                    entry.get("template_name", ""),
                    str(entry.get("updated_at", "")).replace("T", " ")[:19],
                ),
                start=1,
            ):
                self.batch_print_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _set_all_print_checks(self, state):
        for row in range(self.batch_print_table.rowCount()):
            self.batch_print_table.item(row, 0).setCheckState(state)

    def _print_selected_projects(self):
        selected_ids = {
            self.batch_print_table.item(row, 0).data(Qt.UserRole)
            for row in range(self.batch_print_table.rowCount())
            if self.batch_print_table.item(row, 0).checkState() == Qt.Checked
        }
        if not selected_ids:
            QMessageBox.information(self, "Drukowanie zbiorcze", "Zaznacz co najmniej jeden projekt.")
            return
        pages = []
        try:
            for entry in reversed(self.entries):
                if entry.get("archive_id") not in selected_ids:
                    continue
                template = TemplateRegistry.for_project(entry["project"])
                if template:
                    pages.extend(template.renderer_class.render_pages(entry["project"]))
            print_pages(self, pages, "Planora — drukowanie zbiorcze")
        except Exception as exc:
            QMessageBox.warning(self, "Błąd drukowania", str(exc))
