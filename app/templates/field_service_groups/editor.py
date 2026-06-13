from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from app.config import USER_DATA_DIR
from app.core.project_io import ProjectIO
from app.gui.document_preview import DocumentPreview
from app.gui.editor_wizard import EditorWizard, page_layout
from app.gui.responsive import configure_editable_combo, configure_form
from app.templates.field_service_groups.default_project import ROLE_LABELS, ROLE_MEMBER, group, member


class FieldServiceGroupsEditor(QWidget):
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
        self.project.setdefault("template_id", "field_service_groups")
        self.project.setdefault("groups", [])
        self.people = list(people)
        self.renderer = renderer_class
        self.project_path = project_path
        self.animations_enabled = animations_enabled or (lambda: True)
        self.group_index = -1
        self._loading_members = False
        self._compact_members = False
        self.person_fields: list[QComboBox] = []
        self._build_ui(go_back, edit_people)
        self.refresh_groups(0)
        self.select_group(0)
        self.refresh_preview()

    def _build_ui(self, go_back, edit_people):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        toolbar_frame = QWidget()
        toolbar_frame.setObjectName("editorToolbar")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        back = QPushButton("← Menu")
        back.setToolTip("Wróć do menu głównego")
        people_button = QPushButton("Osoby")
        people_button.setToolTip("Otwórz bibliotekę osób")
        save = QPushButton("Zapisz")
        save.setToolTip("Zapisz projekt")
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

        groups_page = QWidget()
        groups_layout = page_layout(
            groups_page,
            "Dokument i grupy",
            "Edytuj nagłówki dokumentu, dodawaj dowolną liczbę grup i ustawiaj ich kolejność.",
        )
        document = QGroupBox("Nagłówek dokumentu")
        form = configure_form(QFormLayout(document))
        self.congregation = QLineEdit(self.project.get("congregation", ""))
        self.title = QLineEdit(self.project.get("title", ""))
        form.addRow("Zbór / miejscowość:", self.congregation)
        form.addRow("Tytuł dokumentu:", self.title)
        groups_layout.addWidget(document)

        group_box = QGroupBox("Grupy w dokumencie")
        group_layout = QVBoxLayout(group_box)
        group_layout.addWidget(self._help("Dodaj lub usuń grupy. Ich kolejność odpowiada kolejności kolumn w eksporcie."))
        self.group_list = QListWidget()
        buttons = QGridLayout()
        add_group = QPushButton("+ Dodaj grupę")
        add_group.setObjectName("primaryButton")
        remove_group = QPushButton("Usuń grupę")
        remove_group.setObjectName("dangerButton")
        up = QPushButton("Wyżej")
        down = QPushButton("Niżej")
        buttons.addWidget(add_group, 0, 0)
        buttons.addWidget(remove_group, 0, 1)
        buttons.addWidget(up, 1, 0)
        buttons.addWidget(down, 1, 1)
        group_layout.addWidget(self.group_list, 1)
        group_layout.addLayout(buttons)
        groups_layout.addWidget(group_box, 1)

        members_page = QWidget()
        members_layout = page_layout(
            members_page,
            "Osoby i role",
            "Wybierz grupę, dodaj osoby z biblioteki i przypisz im role. Nowa osoba jest domyślnie członkiem grupy.",
        )
        self.members_splitter = QSplitter(Qt.Horizontal)
        self.group_side = QGroupBox("Wybierz grupę")
        group_side = self.group_side
        group_side_layout = QVBoxLayout(group_side)
        self.member_group_list = QListWidget()
        group_side_layout.addWidget(self.member_group_list)
        self.members_splitter.addWidget(group_side)

        details = QGroupBox("Wybrana grupa")
        details_layout = QVBoxLayout(details)
        name_form = configure_form(QFormLayout())
        self.member_group_picker = QComboBox()
        self.member_group_picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.member_group_picker.setMinimumContentsLength(12)
        self.group_name = QLineEdit()
        name_form.addRow("Edytowana grupa:", self.member_group_picker)
        name_form.addRow("Nazwa grupy:", self.group_name)
        details_layout.addLayout(name_form)
        details_layout.addWidget(self._help("Kliknij „Dodaj osobę”, wybierz nazwisko i ewentualnie zmień rolę."))
        self.member_table = QTableWidget(0, 2)
        self.member_table.setHorizontalHeaderLabels(["Osoba", "Rola"])
        self.member_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.member_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.member_table.horizontalHeader().resizeSection(1, 230)
        self.member_table.horizontalHeader().setMinimumSectionSize(130)
        self.member_table.verticalHeader().setDefaultSectionSize(46)
        self.member_table.verticalHeader().setMinimumSectionSize(42)
        self.member_table.verticalHeader().setVisible(False)
        self.member_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.member_table.setAlternatingRowColors(True)
        member_buttons = QGridLayout()
        add_member = QPushButton("+ Dodaj osobę")
        add_member.setObjectName("primaryButton")
        remove_member = QPushButton("Usuń osobę")
        remove_member.setObjectName("dangerButton")
        member_up = QPushButton("Wyżej")
        member_down = QPushButton("Niżej")
        member_buttons.addWidget(add_member, 0, 0)
        member_buttons.addWidget(remove_member, 0, 1)
        member_buttons.addWidget(member_up, 1, 0)
        member_buttons.addWidget(member_down, 1, 1)
        details_layout.addWidget(self.member_table, 1)
        details_layout.addLayout(member_buttons)
        self.members_splitter.addWidget(details)
        self.members_splitter.setSizes([280, 900])
        members_layout.addWidget(self.members_splitter, 1)

        preview_page = QWidget()
        preview_layout = page_layout(
            preview_page,
            "Podgląd i eksport",
            "Sprawdź stonowany, czytelny plan, a następnie wyeksportuj go do PDF lub JPG.",
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

        self.wizard.add_step("Grupy", "nagłówek i liczba grup", groups_page)
        self.wizard.add_step("Osoby", "członkowie grup oraz role", members_page)
        self.wizard.add_step("Podgląd", "sprawdzenie i eksport dokumentu", preview_page)

        back.clicked.connect(go_back)
        people_button.clicked.connect(edit_people)
        save.clicked.connect(self.save_project)
        save_as.clicked.connect(self.save_project_as)
        self.congregation.textChanged.connect(self.update_document)
        self.title.textChanged.connect(self.update_document)
        self.group_list.currentRowChanged.connect(self.select_group)
        self.group_list.itemDoubleClicked.connect(lambda _item: self.wizard.set_step(1))
        self.member_group_list.currentRowChanged.connect(self.select_group)
        self.member_group_picker.currentIndexChanged.connect(self.select_group)
        self.group_name.textChanged.connect(self.update_group_name)
        add_group.clicked.connect(self.add_group)
        remove_group.clicked.connect(self.remove_group)
        up.clicked.connect(lambda: self.move_group(-1))
        down.clicked.connect(lambda: self.move_group(1))
        add_member.clicked.connect(self.add_member)
        remove_member.clicked.connect(self.remove_member)
        member_up.clicked.connect(lambda: self.move_member(-1))
        member_down.clicked.connect(lambda: self.move_member(1))
        pdf.clicked.connect(lambda: self._export("pdf"))
        jpg.clicked.connect(lambda: self._export("jpg"))
        both.clicked.connect(lambda: self._export("both"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 1180
        if compact != self._compact_members:
            self._compact_members = compact
            self.group_side.setVisible(not compact)
            self.members_splitter.setOrientation(Qt.Horizontal)
            self.members_splitter.setSizes([0, 1000] if compact else [250, 850])
        self.member_table.horizontalHeader().resizeSection(1, 190 if compact else 230)

    @staticmethod
    def _help(text):
        label = QLabel(text)
        label.setObjectName("helpText")
        label.setWordWrap(True)
        return label

    def _current_group(self):
        groups = self.project.get("groups", [])
        return groups[self.group_index] if 0 <= self.group_index < len(groups) else None

    def update_document(self, *_args):
        self.project["congregation"] = self.congregation.text()
        self.project["title"] = self.title.text()
        self.refresh_preview()

    def refresh_groups(self, selected=None):
        for widget in (self.group_list, self.member_group_list):
            widget.blockSignals(True)
            widget.clear()
            for value in self.project["groups"]:
                count = len(value.get("members", []))
                widget.addItem(f"{value.get('name', 'Grupa')} · {count} os.")
            if selected is not None:
                widget.setCurrentRow(selected)
            widget.blockSignals(False)
        self.member_group_picker.blockSignals(True)
        self.member_group_picker.clear()
        for value in self.project["groups"]:
            count = len(value.get("members", []))
            self.member_group_picker.addItem(f"{value.get('name', 'Grupa')} · {count} os.")
        if selected is not None:
            self.member_group_picker.setCurrentIndex(selected)
        self.member_group_picker.blockSignals(False)

    def select_group(self, index):
        if not 0 <= index < len(self.project["groups"]):
            self.group_index = -1
            self.group_name.clear()
            self._load_members()
            return
        self.group_index = index
        self.group_list.blockSignals(True)
        self.member_group_list.blockSignals(True)
        self.member_group_picker.blockSignals(True)
        self.group_list.setCurrentRow(index)
        self.member_group_list.setCurrentRow(index)
        self.member_group_picker.setCurrentIndex(index)
        self.group_list.blockSignals(False)
        self.member_group_list.blockSignals(False)
        self.member_group_picker.blockSignals(False)
        self.group_name.blockSignals(True)
        self.group_name.setText(self.project["groups"][index].get("name", ""))
        self.group_name.blockSignals(False)
        self._load_members()

    def update_group_name(self, *_args):
        value = self._current_group()
        if value is None:
            return
        value["name"] = self.group_name.text()
        self.refresh_groups(self.group_index)
        self.refresh_preview()

    def add_group(self):
        next_number = len(self.project["groups"]) + 1
        self.project["groups"].append(group(f"GRUPA {next_number}"))
        self.group_index = len(self.project["groups"]) - 1
        self.refresh_groups(self.group_index)
        self.select_group(self.group_index)
        self.refresh_preview()

    def remove_group(self):
        groups = self.project["groups"]
        if 0 <= self.group_index < len(groups):
            groups.pop(self.group_index)
            self.group_index = min(self.group_index, len(groups) - 1)
            self.refresh_groups(self.group_index)
            self.select_group(self.group_index)
            self.refresh_preview()

    def move_group(self, delta):
        groups = self.project["groups"]
        target = self.group_index + delta
        if 0 <= self.group_index < len(groups) and 0 <= target < len(groups):
            groups[self.group_index], groups[target] = groups[target], groups[self.group_index]
            self.group_index = target
            self.refresh_groups(target)
            self.select_group(target)
            self.refresh_preview()

    def _load_members(self):
        self._loading_members = True
        self.person_fields = []
        self.member_table.setRowCount(0)
        value = self._current_group()
        for member_value in value.get("members", []) if value else []:
            self._append_member_row(member_value)
        self._loading_members = False

    def _append_member_row(self, member_value):
        row = self.member_table.rowCount()
        self.member_table.insertRow(row)
        person = configure_editable_combo(QComboBox())
        person.addItem("")
        person.addItems(self.people)
        person.setCurrentText(member_value.get("name", ""))
        role = QComboBox()
        role.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        role.setMinimumContentsLength(8)
        for key, label in ROLE_LABELS.items():
            role.addItem(label, key)
        role_index = role.findData(member_value.get("role", ROLE_MEMBER))
        role.setCurrentIndex(max(0, role_index))
        person.currentTextChanged.connect(self.update_members)
        role.currentIndexChanged.connect(self.update_members)
        self.person_fields.append(person)
        self.member_table.setCellWidget(row, 0, person)
        self.member_table.setCellWidget(row, 1, role)
        self.member_table.setItem(row, 0, QTableWidgetItem())
        self.member_table.setItem(row, 1, QTableWidgetItem())

    def update_members(self, *_args):
        if self._loading_members:
            return
        value = self._current_group()
        if value is None:
            return
        members = []
        for row in range(self.member_table.rowCount()):
            person = self.member_table.cellWidget(row, 0)
            role = self.member_table.cellWidget(row, 1)
            members.append(member(person.currentText(), role.currentData()))
        value["members"] = members
        self.refresh_groups(self.group_index)
        self.refresh_preview()

    def add_member(self):
        value = self._current_group()
        if value is None:
            if not self.project["groups"]:
                self.add_group()
                value = self._current_group()
            else:
                return
        value.setdefault("members", []).append(member())
        self._load_members()
        row = self.member_table.rowCount() - 1
        self.member_table.setCurrentCell(row, 0)
        person = self.member_table.cellWidget(row, 0)
        person.setFocus()
        person.showPopup()
        self.refresh_groups(self.group_index)
        self.refresh_preview()

    def remove_member(self):
        value = self._current_group()
        row = self.member_table.currentRow()
        if value is not None and 0 <= row < len(value.get("members", [])):
            value["members"].pop(row)
            self._load_members()
            self.member_table.setCurrentCell(min(row, self.member_table.rowCount() - 1), 0)
            self.refresh_groups(self.group_index)
            self.refresh_preview()

    def move_member(self, delta):
        value = self._current_group()
        row = self.member_table.currentRow()
        members = value.get("members", []) if value else []
        target = row + delta
        if 0 <= row < len(members) and 0 <= target < len(members):
            members[row], members[target] = members[target], members[row]
            self._load_members()
            self.member_table.setCurrentCell(target, 0)
            self.refresh_preview()

    def refresh_preview(self):
        try:
            pages = self.renderer.render_pages(self.project)
            self.preview.set_image(pages[0].copy(), len(pages))
        except Exception as exc:
            self.preview.set_error(str(exc))

    def set_people(self, people):
        self.people = list(people)
        self._load_members()

    def save_project(self):
        self.update_members()
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
            str(USER_DATA_DIR / "plan-grup-sluzby.json"),
            "Projekt JSON (*.json)",
        )
        if path:
            self.project_path = Path(path)
            self.save_project()

    def _export(self, kind):
        self.update_members()
        default_name = "Plan-grup-sluzby.jpg" if kind == "jpg" else "Plan-grup-sluzby.pdf"
        file_filter = "JPG (*.jpg)" if kind == "jpg" else "PDF (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, "Eksport planu grup", default_name, file_filter)
        if not path:
            return
        try:
            if kind in ("pdf", "both"):
                self.renderer.export_pdf(path, self.project)
            if kind in ("jpg", "both"):
                jpg_path = path if kind == "jpg" else str(Path(path).with_suffix(".jpg"))
                self.renderer.export_jpg(jpg_path, self.project)
            QMessageBox.information(self, "Gotowe", "Plan grup został wyeksportowany.")
        except Exception as exc:
            QMessageBox.warning(self, "Błąd eksportu", str(exc))
