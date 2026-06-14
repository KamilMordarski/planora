from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.project_io import ProjectIO
from app.gui.document_preview import DocumentPreview
from app.gui.editor_wizard import EditorWizard, page_layout
from app.gui.responsive import configure_editable_combo, configure_form


class PublicTalkWatchtowerEditor(QWidget):
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
        self.project.setdefault("template_id", "public_talk_watchtower")
        self.people = people
        self.renderer = renderer_class
        self.project_path = project_path
        self.animations_enabled = animations_enabled or (lambda: True)
        self.current_index = -1
        self._build_ui(go_back, edit_people)
        self.refresh_weeks(0)
        self.select_week(0)
        self.refresh_preview()

    def _build_ui(self, go_back: Callable, edit_people: Callable):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        toolbar_frame = QWidget()
        toolbar_frame.setObjectName("editorToolbar")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
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

        weeks_page = QWidget()
        weeks_layout = page_layout(
            weeks_page,
            "Dokument i tygodnie",
            "Nadaj tytuł dokumentowi, a następnie dodaj lub wybierz tydzień do edycji.",
        )
        title_group = QGroupBox("Ustawienia dokumentu")
        title_form = configure_form(QFormLayout(title_group))
        self.title_edit = QLineEdit(self.project.get("title", ""))
        title_form.addRow("Tytuł dokumentu:", self.title_edit)
        weeks_layout.addWidget(title_group)

        weeks_group = QGroupBox("Tygodnie w projekcie")
        left_layout = QVBoxLayout(weeks_group)
        help_text = QLabel(
            "Nowy tydzień: wybierz „Nowy formularz”, uzupełnij krok „Dane” i kliknij „Dodaj z formularza”. "
            "Kolejność na liście jest kolejnością w eksporcie."
        )
        help_text.setObjectName("helpText")
        help_text.setWordWrap(True)
        left_layout.addWidget(help_text)
        self.week_list = QListWidget()
        left_layout.addWidget(self.week_list)
        new_form = QPushButton("Nowy formularz")
        new_form.setToolTip("Czyści krok „Dane”, aby przygotować nowy tydzień bez zmieniania wybranego wpisu.")
        add = QPushButton("+ Dodaj z formularza")
        add.setToolTip("Dodaje nowy tydzień z datą, osobami i tematami wpisanymi w kroku „Dane”.")
        add.setObjectName("primaryButton")
        delete = QPushButton("Usuń tydzień")
        delete.setObjectName("dangerButton")
        move_row = QHBoxLayout()
        up = QPushButton("Przenieś wyżej")
        down = QPushButton("Przenieś niżej")
        move_row.addWidget(up)
        move_row.addWidget(down)
        left_layout.addWidget(new_form)
        left_layout.addWidget(add)
        left_layout.addWidget(delete)
        left_layout.addLayout(move_row)
        weeks_layout.addWidget(weeks_group, 1)

        data_page = QWidget()
        data_layout = page_layout(
            data_page,
            "Dane wybranego tygodnia",
            "Wybierz rodzaj tygodnia i uzupełnij osoby oraz tematy programu.",
        )
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor = QWidget()
        form = QVBoxLayout(editor)
        basics = QGroupBox("Podstawowe informacje")
        basics_form = configure_form(QFormLayout(basics))
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("np. 14 czerwca 2026")
        self.normal_radio = QRadioButton("Standardowy")
        self.special_radio = QRadioButton("Wydarzenie specjalne")
        type_row = QHBoxLayout()
        type_row.addWidget(self.normal_radio)
        type_row.addWidget(self.special_radio)
        type_row.addStretch()
        basics_form.addRow("Data:", self.date_edit)
        basics_form.addRow("Rodzaj:", type_row)
        form.addWidget(basics)

        self.combo_fields = {}
        self.text_fields = {}
        normal_group = QGroupBox("Wykład publiczny i Studium Strażnicy")
        normal_form = configure_form(QFormLayout(normal_group))
        for key, label, use_combo in [
            ("chairman", "Przewodniczący", True),
            ("lecture_topic", "Temat wykładu", False),
            ("lecturer", "Wykładowca", True),
            ("watchtower_topic", "Temat Strażnicy", False),
            ("watchtower_conductor", "Prowadzący Strażnicę", True),
            ("reader", "Lektor", True),
        ]:
            if use_combo:
                field = configure_editable_combo(QComboBox())
                field.addItem("")
                field.addItems(self.people)
                self.combo_fields[key] = field
            else:
                field = QTextEdit()
                field.setMinimumHeight(65)
                field.setMaximumHeight(100)
                self.text_fields[key] = field
            normal_form.addRow(f"{label}:", field)
        form.addWidget(normal_group)

        special_group = QGroupBox("Wydarzenie specjalne")
        special_layout = QVBoxLayout(special_group)
        special_help = QLabel("To pole zastępuje standardowy program dla wybranego tygodnia.")
        special_help.setObjectName("helpText")
        special_help.setWordWrap(True)
        self.special_text = QTextEdit()
        self.special_text.setMinimumHeight(110)
        special_layout.addWidget(special_help)
        special_layout.addWidget(self.special_text)
        form.addWidget(special_group)
        form_actions = QHBoxLayout()
        new_form_from_data = QPushButton("Wyczyść i przygotuj nowy formularz")
        add_from_data = QPushButton("Dodaj jako nowy tydzień z formularza")
        add_from_data.setObjectName("primaryButton")
        form_actions.addWidget(new_form_from_data)
        form_actions.addWidget(add_from_data)
        form.addLayout(form_actions)
        form.addStretch()
        editor_scroll.setWidget(editor)
        data_layout.addWidget(editor_scroll, 1)

        preview_page = QWidget()
        preview_layout = page_layout(
            preview_page,
            "Podgląd i eksport",
            "Sprawdź cały dokument w dużym podglądzie, a następnie wybierz format eksportu.",
        )
        self.preview = DocumentPreview()
        preview_layout.addWidget(self.preview, 1)
        export_row = QHBoxLayout()
        pdf = QPushButton("Eksportuj PDF")
        jpg = QPushButton("Eksportuj JPG")
        both = QPushButton("Eksportuj PDF + JPG")
        both.setObjectName("primaryButton")
        for button in (pdf, jpg, both):
            export_row.addWidget(button)
        preview_layout.addLayout(export_row)

        self.wizard.add_step("Tygodnie", "tytuł dokumentu i wybór tygodnia", weeks_page)
        self.wizard.add_step("Dane", "osoby, tematy i rodzaj tygodnia", data_page)
        self.wizard.add_step("Podgląd", "sprawdzenie i eksport dokumentu", preview_page)

        back.clicked.connect(go_back)
        people.clicked.connect(edit_people)
        save.clicked.connect(self.save_project)
        save_as.clicked.connect(self.save_project_as)
        self.week_list.currentRowChanged.connect(self.select_week)
        self.week_list.itemDoubleClicked.connect(lambda _item: self.wizard.set_step(1))
        new_form.clicked.connect(self.new_week_form)
        new_form_from_data.clicked.connect(self.new_week_form)
        add.clicked.connect(self.add_week)
        add_from_data.clicked.connect(self.add_week)
        delete.clicked.connect(self.delete_week)
        up.clicked.connect(lambda: self.move_week(-1))
        down.clicked.connect(lambda: self.move_week(1))
        pdf.clicked.connect(self.export_pdf)
        jpg.clicked.connect(self.export_jpg)
        both.clicked.connect(self.export_both)
        for widget in (self.title_edit, self.date_edit, self.special_text):
            widget.textChanged.connect(self.update_current)
        for field in self.combo_fields.values():
            field.currentTextChanged.connect(self.update_current)
        for field in self.text_fields.values():
            field.textChanged.connect(self.update_current)
        self.normal_radio.toggled.connect(self.update_current)

    def refresh_weeks(self, selected: int | None = None):
        self.week_list.blockSignals(True)
        self.week_list.clear()
        for week in self.project.get("weeks", []):
            self.week_list.addItem(week.get("date") or "bez daty")
        if selected is not None:
            self.week_list.setCurrentRow(selected)
        self.week_list.blockSignals(False)

    def select_week(self, index: int):
        weeks = self.project.get("weeks", [])
        if index < 0 or index >= len(weeks):
            return
        self.current_index = index
        week = weeks[index]
        widgets = [self.date_edit, self.normal_radio, self.special_radio, self.special_text]
        widgets += list(self.combo_fields.values()) + list(self.text_fields.values())
        for widget in widgets:
            widget.blockSignals(True)
        self.date_edit.setText(week.get("date", ""))
        self.normal_radio.setChecked(week.get("type") != "special")
        self.special_radio.setChecked(week.get("type") == "special")
        for key, field in self.combo_fields.items():
            field.setCurrentText(week.get(key, ""))
        for key, field in self.text_fields.items():
            field.setPlainText(week.get(key, ""))
        self.special_text.setPlainText(week.get("special_text", ""))
        for widget in widgets:
            widget.blockSignals(False)
        self._update_field_state()

    def _update_field_state(self):
        is_normal = self.normal_radio.isChecked()
        for field in list(self.combo_fields.values()) + list(self.text_fields.values()):
            field.setEnabled(is_normal)
        self.special_text.setEnabled(not is_normal)

    def update_current(self, *_args):
        self.project["title"] = self.title_edit.text()
        if self.current_index < 0:
            self._update_field_state()
            return
        self.project["weeks"][self.current_index].update(self._week_from_form())
        self._update_field_state()
        self.refresh_weeks(self.current_index)
        self.refresh_preview()

    def _week_from_form(self):
        week = {
            "date": self.date_edit.text(),
            "type": "special" if self.special_radio.isChecked() else "normal",
            "special_text": self.special_text.toPlainText(),
        }
        week.update({key: field.currentText() for key, field in self.combo_fields.items()})
        week.update({key: field.toPlainText() for key, field in self.text_fields.items()})
        return week

    def refresh_preview(self):
        try:
            pages = self.renderer.paginate(self.project.get("weeks", []))
            image = self.renderer.render_page(self.project.get("title", ""), pages[0])
            self.preview.set_image(image, len(pages))
        except Exception as exc:
            self.preview.set_error(str(exc))

    def set_people(self, people: list[str]):
        self.people = list(people)
        for field in self.combo_fields.values():
            current = field.currentText()
            field.blockSignals(True)
            field.clear()
            field.addItems(self.people)
            field.setCurrentText(current)
            field.blockSignals(False)

    def add_week(self):
        self.project.setdefault("weeks", []).append(self._week_from_form())
        index = len(self.project["weeks"]) - 1
        self.refresh_weeks(index)
        self.select_week(index)
        self.refresh_preview()

    def new_week_form(self):
        self.current_index = -1
        self.week_list.blockSignals(True)
        self.week_list.setCurrentRow(-1)
        self.week_list.clearSelection()
        self.week_list.blockSignals(False)
        widgets = [self.date_edit, self.normal_radio, self.special_radio, self.special_text]
        widgets += list(self.combo_fields.values()) + list(self.text_fields.values())
        for widget in widgets:
            widget.blockSignals(True)
        self.date_edit.clear()
        self.normal_radio.setChecked(True)
        self.special_radio.setChecked(False)
        for field in self.combo_fields.values():
            field.setCurrentText("")
        for field in self.text_fields.values():
            field.clear()
        self.special_text.clear()
        for widget in widgets:
            widget.blockSignals(False)
        self._update_field_state()
        self.wizard.set_step(1)
        self.date_edit.setFocus()

    def delete_week(self):
        weeks = self.project.get("weeks", [])
        if self.current_index >= 0 and len(weeks) > 1:
            weeks.pop(self.current_index)
            index = min(self.current_index, len(weeks) - 1)
            self.refresh_weeks(index)
            self.select_week(index)
            self.refresh_preview()

    def move_week(self, delta: int):
        weeks = self.project.get("weeks", [])
        target = self.current_index + delta
        if 0 <= self.current_index < len(weeks) and 0 <= target < len(weeks):
            weeks[self.current_index], weeks[target] = weeks[target], weeks[self.current_index]
            self.current_index = target
            self.refresh_weeks(target)
            self.select_week(target)
            self.refresh_preview()

    def save_project(self):
        self.update_current()
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
            str(USER_DATA_DIR / "projekt.json"),
            "Projekt JSON (*.json)",
        )
        if path:
            self.project_path = Path(path)
            self.save_project()

    def export_pdf(self):
        self._export("pdf")

    def export_jpg(self):
        self._export("jpg")

    def export_both(self):
        self._export("both")

    def _export(self, kind: str):
        self.update_current()
        default_name = "Wyklady.jpg" if kind == "jpg" else "Wyklady.pdf"
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
