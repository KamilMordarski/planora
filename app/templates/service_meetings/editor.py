from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.project_io import ProjectIO
from app.gui.document_preview import DocumentPreview
from app.gui.editor_wizard import EditorWizard, page_layout
from app.gui.export_validation import confirm_export
from app.gui.printing import print_project
from app.gui.responsive import configure_editable_combo, configure_form
from app.templates.service_meetings.default_project import DEFAULT_PROJECT, meeting_row


class ServiceMeetingsEditor(QWidget):
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
        self.project.setdefault("template_id", "service_meetings")
        self.project.setdefault("headers", dict(DEFAULT_PROJECT["headers"]))
        self.project.setdefault("colors", dict(DEFAULT_PROJECT["colors"]))
        self.project.setdefault("meetings", [])
        self.people = list(people)
        self.renderer = renderer_class
        self.project_path = project_path
        self.animations_enabled = animations_enabled or (lambda: True)
        self.current_index = -1
        self._loading = False
        self.color_fields: dict[str, QLineEdit] = {}
        self.color_buttons: dict[str, QPushButton] = {}
        self._build_ui(go_back, edit_people)
        self.refresh_meeting_list(0)
        self.select_meeting(0)
        self.refresh_preview()

    def _build_ui(self, go_back, edit_people):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        toolbar_frame = QWidget()
        toolbar_frame.setObjectName("editorToolbar")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        back = QPushButton("← Menu")
        people_button = QPushButton("Biblioteka osób")
        save = QPushButton("Zapisz projekt")
        save.setObjectName("primaryButton")
        save_as = QPushButton("Zapisz jako…")
        toolbar.addWidget(back)
        toolbar.addStretch()
        toolbar.addWidget(people_button)
        toolbar.addWidget(save)
        toolbar.addWidget(save_as)
        root.addWidget(toolbar_frame)

        self.wizard = EditorWizard(self.animations_enabled)
        root.addWidget(self.wizard, 1)

        settings_page = QWidget()
        settings_layout = page_layout(
            settings_page,
            "Wygląd i teksty dokumentu",
            "Edytuj tytuł, okres, nazwy kolumn, notatkę i stonowaną kolorystykę planu.",
        )
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_content = QWidget()
        settings_content_layout = QVBoxLayout(settings_content)

        text_group = QGroupBox("Teksty dokumentu")
        text_form = configure_form(QFormLayout(text_group))
        self.title = QLineEdit(self.project.get("title", ""))
        self.period = QLineEdit(self.project.get("period", ""))
        self.note = QPlainTextEdit(self.project.get("note", ""))
        self.note.setMinimumHeight(80)
        self.note.setMaximumHeight(130)
        text_form.addRow("Tytuł:", self.title)
        text_form.addRow("Okres / podtytuł:", self.period)
        text_form.addRow("Notatka pod tabelą:", self.note)
        settings_content_layout.addWidget(text_group)

        header_group = QGroupBox("Nazwy kolumn")
        header_form = configure_form(QFormLayout(header_group))
        headers = self.project["headers"]
        self.header_fields = {
            "date": QLineEdit(headers.get("date", "")),
            "time": QLineEdit(headers.get("time", "")),
            "place": QLineEdit(headers.get("place", "")),
            "conductor": QLineEdit(headers.get("conductor", "")),
        }
        for key, label in (
            ("date", "Kolumna daty:"),
            ("time", "Kolumna godziny:"),
            ("place", "Kolumna miejsca:"),
            ("conductor", "Kolumna prowadzącego:"),
        ):
            header_form.addRow(label, self.header_fields[key])
        settings_content_layout.addWidget(header_group)

        color_group = QGroupBox("Kolorystyka eksportu")
        color_form = configure_form(QFormLayout(color_group))
        for key, label in (
            ("header_fill", "Tło nagłówka:"),
            ("header_text", "Tekst nagłówka:"),
            ("accent_fill", "Domyślne wyróżnienie daty:"),
            ("note_fill", "Tło notatki:"),
            ("text", "Tekst dokumentu:"),
            ("grid", "Linie tabeli:"),
        ):
            color_form.addRow(label, self._color_control(key, self.project["colors"].get(key, "")))
        settings_content_layout.addWidget(color_group)
        settings_content_layout.addStretch()
        settings_scroll.setWidget(settings_content)
        settings_layout.addWidget(settings_scroll, 1)

        meetings_page = QWidget()
        meetings_layout = page_layout(
            meetings_page,
            "Zbiórki w planie",
            "Dodawaj zbiórki, zmieniaj ich kolejność i edytuj każdą wartość bez ograniczeń.",
        )
        self.meeting_splitter = QSplitter(Qt.Horizontal)
        list_panel = QGroupBox("Lista zbiórek")
        list_layout = QVBoxLayout(list_panel)
        help_label = QLabel(
            "Nowy termin: wybierz „Nowy formularz”, uzupełnij dane po prawej i kliknij „Dodaj z formularza”. "
            "Kolejność na liście jest kolejnością w eksporcie."
        )
        help_label.setObjectName("helpText")
        help_label.setWordWrap(True)
        self.meeting_list = QListWidget()
        new_form = QPushButton("Nowy formularz")
        new_form.setToolTip("Czyści formularz po prawej, aby przygotować nową zbiórkę bez zmieniania wybranego wpisu.")
        add = QPushButton("+ Dodaj z formularza")
        add.setToolTip("Dodaje nową zbiórkę z datą, godziną, miejscem i prowadzącym widocznymi po prawej.")
        add.setObjectName("primaryButton")
        duplicate = QPushButton("Duplikuj zbiórkę")
        remove = QPushButton("Usuń zbiórkę")
        remove.setObjectName("dangerButton")
        move_row = QHBoxLayout()
        up = QPushButton("Wyżej")
        down = QPushButton("Niżej")
        move_row.addWidget(up)
        move_row.addWidget(down)
        list_layout.addWidget(help_label)
        list_layout.addWidget(self.meeting_list, 1)
        list_layout.addWidget(new_form)
        list_layout.addWidget(add)
        list_layout.addWidget(duplicate)
        list_layout.addWidget(remove)
        list_layout.addLayout(move_row)
        self.meeting_splitter.addWidget(list_panel)

        detail_panel = QGroupBox("Wybrana zbiórka")
        detail_form = configure_form(QFormLayout(detail_panel))
        self.date = QLineEdit()
        self.date.setPlaceholderText("np. Wtorek 2 czerwca")
        self.time = QLineEdit()
        self.time.setPlaceholderText("np. 17:15")
        self.place = QLineEdit()
        self.place.setPlaceholderText("np. Sala Królestwa")
        self.conductor = configure_editable_combo(QComboBox())
        self.conductor.addItem("")
        self.conductor.addItems(self.people)
        self.date_color = QLineEdit()
        date_color_row = QHBoxLayout()
        date_color_row.addWidget(self.date_color, 1)
        choose_date_color = QPushButton("Wybierz kolor")
        choose_date_color.clicked.connect(self.choose_row_color)
        date_color_row.addWidget(choose_date_color)
        detail_form.addRow("Data / opis dnia:", self.date)
        detail_form.addRow("Godzina:", self.time)
        detail_form.addRow("Miejsce:", self.place)
        detail_form.addRow("Prowadzący:", self.conductor)
        detail_form.addRow("Wyróżnienie daty:", date_color_row)
        self.meeting_splitter.addWidget(detail_panel)
        self.meeting_splitter.setSizes([430, 850])
        meetings_layout.addWidget(self.meeting_splitter, 1)

        preview_page = QWidget()
        preview_layout = page_layout(
            preview_page,
            "Podgląd i eksport",
            "Sprawdź gotowy plan w stonowanej kolorystyce, a następnie wyeksportuj PDF lub JPG.",
        )
        self.preview = DocumentPreview()
        export_row = QHBoxLayout()
        pdf = QPushButton("Eksportuj PDF")
        jpg = QPushButton("Eksportuj JPG")
        both = QPushButton("Eksportuj PDF + JPG")
        print_button = QPushButton("Drukuj")
        both.setObjectName("primaryButton")
        for button in (print_button, pdf, jpg, both):
            export_row.addWidget(button)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addLayout(export_row)

        self.wizard.add_step("Dokument", "tytuły, kolumny i kolorystyka", settings_page)
        self.wizard.add_step("Zbiórki", "terminy, miejsca i prowadzący", meetings_page)
        self.wizard.add_step("Podgląd", "sprawdzenie i eksport dokumentu", preview_page)

        back.clicked.connect(go_back)
        people_button.clicked.connect(edit_people)
        save.clicked.connect(self.save_project)
        save_as.clicked.connect(self.save_project_as)
        new_form.clicked.connect(self.new_meeting_form)
        add.clicked.connect(self.add_meeting)
        duplicate.clicked.connect(self.duplicate_meeting)
        remove.clicked.connect(self.remove_meeting)
        up.clicked.connect(lambda: self.move_meeting(-1))
        down.clicked.connect(lambda: self.move_meeting(1))
        self.meeting_list.currentRowChanged.connect(self.select_meeting)
        self.meeting_list.itemDoubleClicked.connect(lambda _item: self.wizard.set_step(1))
        for field in (self.title, self.period, self.note, *self.header_fields.values(), *self.color_fields.values()):
            field.textChanged.connect(self.update_document)
        for field in (self.date, self.time, self.place, self.date_color):
            field.textChanged.connect(self.update_meeting)
        self.conductor.currentTextChanged.connect(self.update_meeting)
        pdf.clicked.connect(lambda: self._export("pdf"))
        jpg.clicked.connect(lambda: self._export("jpg"))
        both.clicked.connect(lambda: self._export("both"))
        print_button.clicked.connect(lambda: print_project(self, self.renderer, self.project, "Planora"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        orientation = Qt.Vertical if self.width() < 980 else Qt.Horizontal
        if self.meeting_splitter.orientation() != orientation:
            self.meeting_splitter.setOrientation(orientation)
            self.meeting_splitter.setSizes([370, 680])

    def _color_control(self, key, value):
        row = QHBoxLayout()
        field = QLineEdit(value)
        field.setPlaceholderText("#425466")
        button = QPushButton("Wybierz kolor")
        button.clicked.connect(lambda _checked=False, color_key=key: self.choose_document_color(color_key))
        row.addWidget(field, 1)
        row.addWidget(button)
        self.color_fields[key] = field
        self.color_buttons[key] = button
        return row

    def choose_document_color(self, key):
        field = self.color_fields[key]
        color = QColorDialog.getColor(QColor(field.text() or DEFAULT_PROJECT["colors"][key]), self, "Wybierz kolor")
        if color.isValid():
            field.setText(color.name())

    def choose_row_color(self):
        fallback = self.project.get("colors", {}).get("accent_fill", "#dbe7ee")
        color = QColorDialog.getColor(QColor(self.date_color.text() or fallback), self, "Wybierz kolor daty")
        if color.isValid():
            self.date_color.setText(color.name())

    def update_document(self, *_args):
        if self._loading:
            return
        self.project["title"] = self.title.text()
        self.project["period"] = self.period.text()
        self.project["note"] = self.note.toPlainText()
        self.project["headers"] = {key: field.text() for key, field in self.header_fields.items()}
        self.project["colors"] = {key: field.text() for key, field in self.color_fields.items()}
        self.refresh_preview()

    def refresh_meeting_list(self, selected=None):
        self.meeting_list.blockSignals(True)
        self.meeting_list.clear()
        for row in self.project["meetings"]:
            label = row.get("date") or "Bez daty"
            if row.get("time"):
                label += f" · {row['time']}"
            if row.get("place"):
                label += f" · {row['place']}"
            self.meeting_list.addItem(label)
        if selected is not None:
            self.meeting_list.setCurrentRow(selected)
        self.meeting_list.blockSignals(False)

    def select_meeting(self, index):
        rows = self.project["meetings"]
        if not 0 <= index < len(rows):
            self.current_index = -1
            self._load_row(meeting_row())
            return
        self.current_index = index
        self._load_row(rows[index])

    def _load_row(self, row):
        self._loading = True
        self.date.setText(row.get("date", ""))
        self.time.setText(row.get("time", ""))
        self.place.setText(row.get("place", ""))
        self.conductor.setCurrentText(row.get("conductor", ""))
        self.date_color.setText(row.get("date_color", ""))
        self._loading = False

    def update_meeting(self, *_args):
        if self._loading or not 0 <= self.current_index < len(self.project["meetings"]):
            return
        self.project["meetings"][self.current_index].update(self._meeting_from_form())
        self.refresh_meeting_list(self.current_index)
        self.refresh_preview()

    def _meeting_from_form(self):
        return meeting_row(
            self.date.text(),
            self.time.text(),
            self.place.text(),
            self.conductor.currentText(),
            self.date_color.text(),
        )

    def add_meeting(self):
        self.project["meetings"].append(self._meeting_from_form())
        self.current_index = len(self.project["meetings"]) - 1
        self.refresh_meeting_list(self.current_index)
        self.select_meeting(self.current_index)
        self.refresh_preview()

    def new_meeting_form(self):
        self.current_index = -1
        self.meeting_list.blockSignals(True)
        self.meeting_list.setCurrentRow(-1)
        self.meeting_list.clearSelection()
        self.meeting_list.blockSignals(False)
        self._load_row(meeting_row())
        self.date.setFocus()

    def duplicate_meeting(self):
        if not 0 <= self.current_index < len(self.project["meetings"]):
            return
        self.project["meetings"].insert(self.current_index + 1, dict(self.project["meetings"][self.current_index]))
        self.current_index += 1
        self.refresh_meeting_list(self.current_index)
        self.select_meeting(self.current_index)
        self.refresh_preview()

    def remove_meeting(self):
        if 0 <= self.current_index < len(self.project["meetings"]):
            self.project["meetings"].pop(self.current_index)
            self.current_index = min(self.current_index, len(self.project["meetings"]) - 1)
            self.refresh_meeting_list(self.current_index)
            self.select_meeting(self.current_index)
            self.refresh_preview()

    def move_meeting(self, delta):
        rows = self.project["meetings"]
        target = self.current_index + delta
        if 0 <= self.current_index < len(rows) and 0 <= target < len(rows):
            rows[self.current_index], rows[target] = rows[target], rows[self.current_index]
            self.current_index = target
            self.refresh_meeting_list(target)
            self.select_meeting(target)
            self.refresh_preview()

    def refresh_preview(self):
        try:
            pages = self.renderer.render_pages(self.project)
            self.preview.set_image(pages[0].copy(), len(pages))
        except Exception as exc:
            self.preview.set_error(str(exc))

    def set_people(self, people):
        current = self.conductor.currentText()
        self.people = list(people)
        self.conductor.blockSignals(True)
        self.conductor.clear()
        self.conductor.addItem("")
        self.conductor.addItems(self.people)
        self.conductor.setCurrentText(current)
        self.conductor.blockSignals(False)

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
            str(USER_DATA_DIR / "zbiorki-do-sluzby.json"),
            "Projekt JSON (*.json)",
        )
        if path:
            self.project_path = Path(path)
            self.save_project()

    def _export(self, kind):
        if not confirm_export(self, self.project):
            return
        default_name = "Zbiorki-do-sluzby.jpg" if kind == "jpg" else "Zbiorki-do-sluzby.pdf"
        file_filter = "JPG (*.jpg)" if kind == "jpg" else "PDF (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, "Eksport planu zbiórek", default_name, file_filter)
        if not path:
            return
        try:
            if kind in ("pdf", "both"):
                self.renderer.export_pdf(path, self.project)
            if kind in ("jpg", "both"):
                jpg_path = path if kind == "jpg" else str(Path(path).with_suffix(".jpg"))
                self.renderer.export_jpg(jpg_path, self.project)
            QMessageBox.information(self, "Gotowe", "Plan zbiórek został wyeksportowany.")
        except Exception as exc:
            QMessageBox.warning(self, "Błąd eksportu", str(exc))
