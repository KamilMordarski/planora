from collections.abc import Callable
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.project_io import ProjectIO
from app.gui.document_preview import DocumentPreview
from app.gui.editor_wizard import EditorWizard, page_layout
from app.gui.responsive import configure_editable_combo, configure_form
from app.templates.cleaning_attendants.conflicts import find_conflicts
from app.templates.cleaning_attendants.default_project import attendant_row, weekly_row


class CleaningAttendantsEditor(QWidget):
    def __init__(
        self,
        project: dict,
        people: list[str],
        renderer_class,
        project_path: Path | None,
        go_back: Callable,
        edit_people: Callable,
        animations_enabled: Callable[[], bool] | None = None,
    ):
        super().__init__()
        self.project = project
        self.project.setdefault("template_id", "cleaning_attendants")
        self.project.setdefault("weekly_assignments", [])
        self.project.setdefault("attendant_assignments", [])
        self.people = list(people)
        self.renderer = renderer_class
        self.project_path = project_path
        self.animations_enabled = animations_enabled or (lambda: True)
        self.weekly_index = -1
        self.attendant_index = -1
        self.person_fields: list[QComboBox] = []
        self._build_ui(go_back, edit_people)
        self.refresh_weekly_list(0)
        self.refresh_attendant_list(0)
        self.select_weekly(0)
        self.select_attendant(0)
        self.refresh_all()

    def _build_ui(self, go_back: Callable, edit_people: Callable):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        toolbar_frame = QWidget()
        toolbar_frame.setObjectName("editorToolbar")
        toolbar = QHBoxLayout(toolbar_frame)
        back = QPushButton("← Wróć do menu")
        people = QPushButton("Biblioteka osób")
        save = QPushButton("Zapisz projekt")
        save.setObjectName("primaryButton")
        save_as = QPushButton("Zapisz jako…")
        toolbar.addWidget(back)
        toolbar.addStretch()
        toolbar.addWidget(people)
        toolbar.addWidget(save)
        toolbar.addWidget(save_as)
        root.addWidget(toolbar_frame, 0)

        self.wizard = EditorWizard(self.animations_enabled)
        root.addWidget(self.wizard, 1)

        settings_page = QWidget()
        settings_layout = page_layout(
            settings_page,
            "Ustawienia dokumentu",
            "Nadaj tytuły obu częściom grafiku. Te ustawienia można później zmienić.",
        )
        settings_form = configure_form(QFormLayout())
        self.title_edit = QPlainTextEdit(self.project.get("title", ""))
        self.title_edit.setMinimumHeight(100)
        self.title_edit.setMaximumHeight(150)
        self.attendant_title_edit = QLineEdit(self.project.get("attendant_title", ""))
        settings_form.addRow("Tytuł planu sprzątania:", self.title_edit)
        settings_form.addRow("Tytuł planu porządkowych:", self.attendant_title_edit)
        settings_layout.addLayout(settings_form)
        settings_layout.addStretch()

        weekly_page = QWidget()
        weekly_layout = page_layout(
            weekly_page,
            "Sprzątanie i nagłośnienie",
            "Dodaj zakresy tygodniowe i przypisz grupę, sprzątanie, konsolę oraz mikrofony.",
        )
        weekly_layout.addWidget(self._build_weekly_tab(), 1)

        attendants_page = QWidget()
        attendants_layout = page_layout(
            attendants_page,
            "Służba porządkowa i kontrola kolizji",
            "Przypisz porządkowych do konkretnych dat. Ostrzeżenia pojawią się automatycznie.",
        )
        self.attendants_splitter = QSplitter()
        attendants_splitter = self.attendants_splitter
        attendants_splitter.addWidget(self._build_attendant_tab())
        conflicts = QWidget()
        conflict_layout = QVBoxLayout(conflicts)
        conflict_title = QLabel("Kontrola kolizji obowiązków")
        conflict_title.setObjectName("cardTitle")
        self.conflict_summary = QLabel()
        self.conflict_list = QListWidget()
        conflict_layout.addWidget(conflict_title)
        conflict_layout.addWidget(self.conflict_summary)
        conflict_layout.addWidget(self.conflict_list, 1)
        attendants_splitter.addWidget(conflicts)
        attendants_splitter.setSizes([700, 500])
        attendants_layout.addWidget(attendants_splitter, 1)

        preview_page = QWidget()
        preview_layout = page_layout(
            preview_page,
            "Podgląd i eksport",
            "Sprawdź cały dokument w dużym podglądzie, a następnie wybierz format eksportu.",
        )
        self.preview = DocumentPreview()
        export_row = QHBoxLayout()
        pdf = QPushButton("Eksportuj PDF")
        jpg = QPushButton("Eksportuj JPG")
        both = QPushButton("Eksportuj PDF + JPG")
        both.setObjectName("primaryButton")
        for button in (pdf, jpg, both):
            export_row.addWidget(button)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addLayout(export_row)

        self.wizard.add_step("Ustawienia", "tytuły dokumentu", settings_page)
        self.wizard.add_step("Sprzątanie", "tygodnie i obsługa nagłośnienia", weekly_page)
        self.wizard.add_step("Porządkowi", "daty oraz kontrola kolizji", attendants_page)
        self.wizard.add_step("Podgląd", "sprawdzenie i eksport dokumentu", preview_page)
        self.wizard.step_changed.connect(lambda _index: self._update_responsive_layout())

        back.clicked.connect(go_back)
        people.clicked.connect(edit_people)
        save.clicked.connect(self.save_project)
        save_as.clicked.connect(self.save_project_as)
        pdf.clicked.connect(lambda: self._export("pdf"))
        jpg.clicked.connect(lambda: self._export("jpg"))
        both.clicked.connect(lambda: self._export("both"))
        self.title_edit.textChanged.connect(self.update_titles)
        self.attendant_title_edit.textChanged.connect(self.update_titles)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        orientation = Qt.Vertical if self.width() < 1050 else Qt.Horizontal
        if self.attendants_splitter.orientation() != orientation:
            self.attendants_splitter.setOrientation(orientation)
            self.attendants_splitter.setSizes([650, 350])
        for splitter in (self.weekly_editor_splitter, self.attendant_editor_splitter):
            if splitter.orientation() != orientation:
                splitter.setOrientation(orientation)
                splitter.setSizes([330, 650] if orientation == Qt.Vertical else [360, 760])

    def _build_weekly_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        self.weekly_editor_splitter = QSplitter(Qt.Horizontal)
        list_panel = QWidget()
        list_side = QVBoxLayout(list_panel)
        list_side.addWidget(self._help_label(
            "Nowy tydzień: wybierz „Nowy formularz”, przypisz daty, grupę i osoby, potem kliknij „Dodaj z formularza”."
        ))
        self.weekly_list = QListWidget()
        new_form = QPushButton("Nowy formularz")
        add = QPushButton("+ Dodaj z formularza")
        add.setToolTip("Dodaje tydzień wraz z aktualnie wpisanymi datami, grupą i osobami.")
        delete = QPushButton("Usuń tydzień")
        delete.setObjectName("dangerButton")
        move = QHBoxLayout()
        up = QPushButton("Wyżej")
        down = QPushButton("Niżej")
        move.addWidget(up)
        move.addWidget(down)
        list_side.addWidget(self.weekly_list)
        list_side.addWidget(new_form)
        list_side.addWidget(add)
        list_side.addWidget(delete)
        list_side.addLayout(move)
        self.weekly_editor_splitter.addWidget(list_panel)

        form_panel = QWidget()
        form = configure_form(QFormLayout(form_panel))
        self.start_date = self._date_edit()
        self.end_date = self._date_edit()
        self.group = QComboBox()
        configure_editable_combo(self.group, 5)
        self.group.addItems(["I", "II", "III", "IV", "V"])
        self.cleaning_person = self._person_combo()
        self.console_person = self._person_combo()
        self.microphone_1 = self._person_combo()
        self.microphone_2 = self._person_combo()
        form.addRow("Początek zakresu:", self.start_date)
        form.addRow("Koniec zakresu:", self.end_date)
        form.addRow("Grupa:", self.group)
        form.addRow("Sprzątanie sali:", self.cleaning_person)
        form.addRow("Konsola Zoom:", self.console_person)
        form.addRow("Mikrofon 1:", self.microphone_1)
        form.addRow("Mikrofon 2:", self.microphone_2)
        self.weekly_editor_splitter.addWidget(form_panel)
        self.weekly_editor_splitter.setSizes([360, 760])
        layout.addWidget(self.weekly_editor_splitter)

        self.weekly_list.currentRowChanged.connect(self.select_weekly)
        new_form.clicked.connect(self.new_weekly_form)
        add.clicked.connect(self.add_weekly)
        delete.clicked.connect(self.delete_weekly)
        up.clicked.connect(lambda: self.move_weekly(-1))
        down.clicked.connect(lambda: self.move_weekly(1))
        for field in (self.start_date, self.end_date):
            field.dateChanged.connect(self.update_weekly)
        for field in (self.group, self.cleaning_person, self.console_person, self.microphone_1, self.microphone_2):
            field.currentTextChanged.connect(self.update_weekly)
        return tab

    def _build_attendant_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        self.attendant_editor_splitter = QSplitter(Qt.Horizontal)
        list_panel = QWidget()
        list_side = QVBoxLayout(list_panel)
        list_side.addWidget(self._help_label(
            "Nowy dyżur: wybierz „Nowy formularz”, ustaw datę i porządkowych, potem kliknij „Dodaj z formularza”."
        ))
        self.attendant_list = QListWidget()
        new_form = QPushButton("Nowy formularz")
        add = QPushButton("+ Dodaj z formularza")
        add.setToolTip("Dodaje datę zebrania wraz z aktualnie wybranymi porządkowymi.")
        delete = QPushButton("Usuń datę")
        delete.setObjectName("dangerButton")
        move = QHBoxLayout()
        up = QPushButton("Wyżej")
        down = QPushButton("Niżej")
        move.addWidget(up)
        move.addWidget(down)
        list_side.addWidget(self.attendant_list)
        list_side.addWidget(new_form)
        list_side.addWidget(add)
        list_side.addWidget(delete)
        list_side.addLayout(move)
        self.attendant_editor_splitter.addWidget(list_panel)

        form_panel = QWidget()
        form = configure_form(QFormLayout(form_panel))
        self.meeting_date = self._date_edit()
        self.lobby_attendant = self._person_combo()
        self.hall_attendant = self._person_combo()
        form.addRow("Data zebrania:", self.meeting_date)
        form.addRow("Porządkowy hol:", self.lobby_attendant)
        form.addRow("Porządkowy sala:", self.hall_attendant)
        self.attendant_editor_splitter.addWidget(form_panel)
        self.attendant_editor_splitter.setSizes([360, 760])
        layout.addWidget(self.attendant_editor_splitter)

        self.attendant_list.currentRowChanged.connect(self.select_attendant)
        new_form.clicked.connect(self.new_attendant_form)
        add.clicked.connect(self.add_attendant)
        delete.clicked.connect(self.delete_attendant)
        up.clicked.connect(lambda: self.move_attendant(-1))
        down.clicked.connect(lambda: self.move_attendant(1))
        self.meeting_date.dateChanged.connect(self.update_attendant)
        self.lobby_attendant.currentTextChanged.connect(self.update_attendant)
        self.hall_attendant.currentTextChanged.connect(self.update_attendant)
        return tab

    @staticmethod
    def _help_label(text):
        label = QLabel(text)
        label.setObjectName("helpText")
        label.setWordWrap(True)
        return label

    def _date_edit(self):
        field = QDateEdit()
        field.setCalendarPopup(True)
        field.setDisplayFormat("dd.MM.yyyy")
        field.setDate(QDate.currentDate())
        return field

    def _person_combo(self):
        field = configure_editable_combo(QComboBox())
        field.addItem("")
        field.addItems(self.people)
        self.person_fields.append(field)
        return field

    @staticmethod
    def _set_date(field: QDateEdit, value: str):
        parsed = QDate.fromString(value, "yyyy-MM-dd")
        field.setDate(parsed if parsed.isValid() else QDate.currentDate())

    @staticmethod
    def _iso_date(field: QDateEdit) -> str:
        return field.date().toString("yyyy-MM-dd")

    @staticmethod
    def _short_date(value: str) -> str:
        try:
            parsed = date.fromisoformat(value)
            return parsed.strftime("%d.%m.%Y")
        except (TypeError, ValueError):
            return "bez daty"

    def update_titles(self, *_args):
        self.project["title"] = self.title_edit.toPlainText()
        self.project["attendant_title"] = self.attendant_title_edit.text()
        self.refresh_preview()

    def refresh_weekly_list(self, selected: int | None = None):
        self.weekly_list.blockSignals(True)
        self.weekly_list.clear()
        for row in self.project["weekly_assignments"]:
            label = f"{self._short_date(row.get('start_date', ''))} – {self._short_date(row.get('end_date', ''))}"
            if row.get("group"):
                label += f" | grupa {row['group']}"
            self.weekly_list.addItem(label)
        if selected is not None:
            self.weekly_list.setCurrentRow(selected)
        self.weekly_list.blockSignals(False)

    def refresh_attendant_list(self, selected: int | None = None):
        self.attendant_list.blockSignals(True)
        self.attendant_list.clear()
        for row in self.project["attendant_assignments"]:
            self.attendant_list.addItem(self._short_date(row.get("date", "")))
        if selected is not None:
            self.attendant_list.setCurrentRow(selected)
        self.attendant_list.blockSignals(False)

    def select_weekly(self, index: int):
        rows = self.project["weekly_assignments"]
        if not 0 <= index < len(rows):
            return
        self.weekly_index = index
        row = rows[index]
        fields = [
            self.start_date,
            self.end_date,
            self.group,
            self.cleaning_person,
            self.console_person,
            self.microphone_1,
            self.microphone_2,
        ]
        for field in fields:
            field.blockSignals(True)
        self._set_date(self.start_date, row.get("start_date", ""))
        self._set_date(self.end_date, row.get("end_date", ""))
        self.group.setCurrentText(row.get("group", ""))
        self.cleaning_person.setCurrentText(row.get("cleaning_person", ""))
        self.console_person.setCurrentText(row.get("console_person", ""))
        self.microphone_1.setCurrentText(row.get("microphone_1", ""))
        self.microphone_2.setCurrentText(row.get("microphone_2", ""))
        for field in fields:
            field.blockSignals(False)

    def select_attendant(self, index: int):
        rows = self.project["attendant_assignments"]
        if not 0 <= index < len(rows):
            return
        self.attendant_index = index
        row = rows[index]
        fields = [self.meeting_date, self.lobby_attendant, self.hall_attendant]
        for field in fields:
            field.blockSignals(True)
        self._set_date(self.meeting_date, row.get("date", ""))
        self.lobby_attendant.setCurrentText(row.get("lobby_attendant", ""))
        self.hall_attendant.setCurrentText(row.get("hall_attendant", ""))
        for field in fields:
            field.blockSignals(False)

    def update_weekly(self, *_args):
        rows = self.project["weekly_assignments"]
        if not 0 <= self.weekly_index < len(rows):
            return
        rows[self.weekly_index].update(self._weekly_from_form())
        self.refresh_weekly_list(self.weekly_index)
        self.refresh_all()

    def update_attendant(self, *_args):
        rows = self.project["attendant_assignments"]
        if not 0 <= self.attendant_index < len(rows):
            return
        rows[self.attendant_index].update(self._attendant_from_form())
        self.refresh_attendant_list(self.attendant_index)
        self.refresh_all()

    def _weekly_from_form(self):
        return weekly_row(
            self._iso_date(self.start_date),
            self._iso_date(self.end_date),
            self.group.currentText(),
            self.cleaning_person.currentText(),
            self.console_person.currentText(),
            self.microphone_1.currentText(),
            self.microphone_2.currentText(),
        )

    def _attendant_from_form(self):
        return attendant_row(
            self._iso_date(self.meeting_date),
            self.lobby_attendant.currentText(),
            self.hall_attendant.currentText(),
        )

    def add_weekly(self):
        self.project["weekly_assignments"].append(self._weekly_from_form())
        self.weekly_index = len(self.project["weekly_assignments"]) - 1
        self.refresh_weekly_list(self.weekly_index)
        self.select_weekly(self.weekly_index)
        self.refresh_all()

    def new_weekly_form(self):
        self.weekly_index = -1
        self.weekly_list.blockSignals(True)
        self.weekly_list.setCurrentRow(-1)
        self.weekly_list.clearSelection()
        self.weekly_list.blockSignals(False)
        fields = [
            self.start_date,
            self.end_date,
            self.group,
            self.cleaning_person,
            self.console_person,
            self.microphone_1,
            self.microphone_2,
        ]
        for field in fields:
            field.blockSignals(True)
        today = QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today.addDays(4))
        self.group.setCurrentText("I")
        for field in (self.cleaning_person, self.console_person, self.microphone_1, self.microphone_2):
            field.setCurrentText("")
        for field in fields:
            field.blockSignals(False)
        self.start_date.setFocus()

    def delete_weekly(self):
        rows = self.project["weekly_assignments"]
        if 0 <= self.weekly_index < len(rows):
            rows.pop(self.weekly_index)
            self.weekly_index = min(self.weekly_index, len(rows) - 1)
            self.refresh_weekly_list(self.weekly_index)
            self.select_weekly(self.weekly_index)
            self.refresh_all()

    def move_weekly(self, delta: int):
        rows = self.project["weekly_assignments"]
        target = self.weekly_index + delta
        if 0 <= self.weekly_index < len(rows) and 0 <= target < len(rows):
            rows[self.weekly_index], rows[target] = rows[target], rows[self.weekly_index]
            self.weekly_index = target
            self.refresh_weekly_list(target)
            self.select_weekly(target)
            self.refresh_all()

    def add_attendant(self):
        self.project["attendant_assignments"].append(self._attendant_from_form())
        self.attendant_index = len(self.project["attendant_assignments"]) - 1
        self.refresh_attendant_list(self.attendant_index)
        self.select_attendant(self.attendant_index)
        self.refresh_all()

    def new_attendant_form(self):
        self.attendant_index = -1
        self.attendant_list.blockSignals(True)
        self.attendant_list.setCurrentRow(-1)
        self.attendant_list.clearSelection()
        self.attendant_list.blockSignals(False)
        fields = [self.meeting_date, self.lobby_attendant, self.hall_attendant]
        for field in fields:
            field.blockSignals(True)
        self.meeting_date.setDate(QDate.currentDate())
        self.lobby_attendant.setCurrentText("")
        self.hall_attendant.setCurrentText("")
        for field in fields:
            field.blockSignals(False)
        self.meeting_date.setFocus()

    def delete_attendant(self):
        rows = self.project["attendant_assignments"]
        if 0 <= self.attendant_index < len(rows):
            rows.pop(self.attendant_index)
            self.attendant_index = min(self.attendant_index, len(rows) - 1)
            self.refresh_attendant_list(self.attendant_index)
            self.select_attendant(self.attendant_index)
            self.refresh_all()

    def move_attendant(self, delta: int):
        rows = self.project["attendant_assignments"]
        target = self.attendant_index + delta
        if 0 <= self.attendant_index < len(rows) and 0 <= target < len(rows):
            rows[self.attendant_index], rows[target] = rows[target], rows[self.attendant_index]
            self.attendant_index = target
            self.refresh_attendant_list(target)
            self.select_attendant(target)
            self.refresh_all()

    def refresh_all(self):
        self.refresh_conflicts()
        self.refresh_preview()

    def refresh_conflicts(self):
        conflicts = find_conflicts(self.project)
        self.conflict_list.clear()
        if not conflicts:
            self.conflict_summary.setText("Brak wykrytych kolizji.")
            self.conflict_summary.setStyleSheet("color: #16713d; font-weight: 600;")
            return
        self.conflict_summary.setText(f"Wykryto kolizje: {len(conflicts)}")
        self.conflict_summary.setStyleSheet("color: #b42318; font-weight: 700;")
        for conflict in conflicts:
            label = f"{self._short_date(conflict['date'])}: {conflict['person']} — {', '.join(conflict['roles'])}"
            item = QListWidgetItem(label)
            item.setForeground(QColor("#b42318"))
            self.conflict_list.addItem(item)

    def refresh_preview(self):
        try:
            pages = self.renderer.render_pages(self.project)
            image = pages[0].copy()
            self.preview.set_image(image, len(pages))
        except Exception as exc:
            self.preview.set_error(str(exc))

    def set_people(self, people: list[str]):
        self.people = list(people)
        for field in self.person_fields:
            current = field.currentText()
            field.blockSignals(True)
            field.clear()
            field.addItem("")
            field.addItems(self.people)
            field.setCurrentText(current)
            field.blockSignals(False)

    def save_project(self):
        if self.project_path is None:
            return self.save_project_as()
        try:
            ProjectIO.save_project(self.project_path, self.project)
            QMessageBox.information(self, "Zapisano", f"Projekt zapisany:\n{self.project_path}")
        except OSError as exc:
            QMessageBox.warning(self, "Błąd zapisu", str(exc))

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Zapisz projekt",
            str(USER_DATA_DIR / "sprzatanie-i-porzadkowi.json"),
            "Projekt JSON (*.json)",
        )
        if path:
            self.project_path = Path(path)
            self.save_project()

    def _export(self, kind: str):
        default_name = "Sprzatanie-i-porzadkowi.jpg" if kind == "jpg" else "Sprzatanie-i-porzadkowi.pdf"
        file_filter = "JPG (*.jpg)" if kind == "jpg" else "PDF (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, "Eksport grafiku", default_name, file_filter)
        if not path:
            return
        try:
            if kind in ("pdf", "both"):
                self.renderer.export_pdf(path, self.project)
            if kind in ("jpg", "both"):
                jpg_path = path if kind == "jpg" else str(Path(path).with_suffix(".jpg"))
                self.renderer.export_jpg(jpg_path, self.project)
            QMessageBox.information(self, "Gotowe", "Grafik został wyeksportowany.")
        except Exception as exc:
            QMessageBox.warning(self, "Błąd eksportu", str(exc))
