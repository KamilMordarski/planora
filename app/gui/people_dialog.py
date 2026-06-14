from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.people_roles import ALL_ROLES, ROLE_OPTIONS, normalize_profiles
from app.core.project_io import ProjectIO
from app.gui.responsive import ResponsiveActionBar


class PeopleDialog(QDialog):
    def __init__(self, people: list[str], profiles: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteka osób")
        self.resize(920, 680)
        self.people = list(people)
        self.profiles = normalize_profiles(self.people, profiles)
        self.role_checks: dict[str, QCheckBox] = {}
        self._loading_roles = False

        layout = QVBoxLayout(self)
        title = QLabel("Biblioteka osób")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Jedna lista nazwisk i uprawnień używana przez wszystkie generatory oraz asystenta.")
        subtitle.setObjectName("screenSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        people_panel = QWidget()
        people_layout = QVBoxLayout(people_panel)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Szukaj osoby…")
        self.search.setClearButtonEnabled(True)
        people_layout.addWidget(self.search)

        import_json = QPushButton("Importuj listę JSON")
        import_json.setToolTip("Dodaje osoby i odtwarza ich uprawnienia z pliku JSON bez usuwania obecnej listy.")
        export_json = QPushButton("Eksportuj listę JSON")
        export_json.setToolTip("Zapisuje nazwiska i wszystkie przypisane uprawnienia w jednym pliku JSON.")
        people_layout.addWidget(ResponsiveActionBar([import_json, export_json], 150, 2))

        self.list_widget = QListWidget()
        self.list_widget.addItems(self.people)
        people_layout.addWidget(self.list_widget)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Imię i nazwisko")
        people_layout.addWidget(self.input)
        add = QPushButton("Dodaj osobę")
        add.setObjectName("primaryButton")
        edit = QPushButton("Zmień")
        delete = QPushButton("Usuń")
        delete.setObjectName("dangerButton")
        people_layout.addWidget(ResponsiveActionBar([add, edit, delete], 100, 3))

        count = QLabel()
        count.setObjectName("screenSubtitle")
        count.setAlignment(Qt.AlignRight)
        people_layout.addWidget(count)
        self.count = count
        splitter.addWidget(people_panel)

        roles_group = QGroupBox("Role i uprawnienia wybranej osoby")
        roles_layout = QVBoxLayout(roles_group)
        roles_help = QLabel(
            "Asystent układania wybiera tylko osoby z odpowiednim uprawnieniem. "
            "Nowe oraz istniejące osoby mają początkowo zaznaczone wszystkie role."
        )
        roles_help.setObjectName("helpText")
        roles_help.setWordWrap(True)
        roles_layout.addWidget(roles_help)
        all_roles = QPushButton("Zaznacz wszystkie")
        no_roles = QPushButton("Wyczyść")
        roles_layout.addWidget(ResponsiveActionBar([all_roles, no_roles], 130, 2))
        roles_scroll = QScrollArea()
        roles_scroll.setWidgetResizable(True)
        roles_content = QWidget()
        roles_content_layout = QVBoxLayout(roles_content)
        for role, label in ROLE_OPTIONS.items():
            check = QCheckBox(label)
            check.toggled.connect(self.update_selected_roles)
            self.role_checks[role] = check
            roles_content_layout.addWidget(check)
        roles_content_layout.addStretch()
        roles_scroll.setWidget(roles_content)
        roles_layout.addWidget(roles_scroll, 1)
        splitter.addWidget(roles_group)
        splitter.setSizes([430, 470])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        self.search.textChanged.connect(self.filter_people)
        import_json.clicked.connect(self.import_json)
        export_json.clicked.connect(self.export_json)
        add.clicked.connect(self.add_person)
        edit.clicked.connect(self.edit_person)
        delete.clicked.connect(self.delete_person)
        self.list_widget.currentTextChanged.connect(self.select_person)
        all_roles.clicked.connect(lambda: self.set_selected_roles(ALL_ROLES))
        no_roles.clicked.connect(lambda: self.set_selected_roles(()))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.update_count()
        if self.people:
            self.list_widget.setCurrentRow(0)

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importuj listę osób",
            str(USER_DATA_DIR),
            "Lista osób JSON (*.json)",
        )
        if not path:
            return
        try:
            self.people, self.profiles, added, roles_updated = ProjectIO.import_people_library(
                Path(path),
                self.people,
                self.profiles,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Nie można zaimportować listy", str(exc))
            return
        self.refresh_list()
        QMessageBox.information(
            self,
            "Import zakończony",
            f"Dodano nowych osób: {added}\nZaktualizowano uprawnienia: {roles_updated}\n"
            f"Łączna liczba osób: {len(self.people)}",
        )

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Eksportuj bibliotekę osób",
            str(USER_DATA_DIR / "planora-biblioteka-osob.json"),
            "Biblioteka osób JSON (*.json)",
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.casefold() != ".json":
            destination = destination.with_suffix(".json")
        try:
            ProjectIO.export_people_library(destination, self.people, self.profiles)
        except OSError as exc:
            QMessageBox.warning(self, "Nie można wyeksportować listy", str(exc))
            return
        QMessageBox.information(
            self,
            "Eksport zakończony",
            f"Zapisano osoby wraz z uprawnieniami:\n{destination}",
        )

    def refresh_list(self):
        phrase = self.search.text()
        self.list_widget.clear()
        self.list_widget.addItems(self.people)
        self.filter_people(phrase)
        self.update_count()

    def update_count(self):
        self.count.setText(f"Liczba osób: {len(self.people)}")

    def filter_people(self, text):
        phrase = text.casefold().strip()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item.setHidden(phrase not in item.text().casefold())

    def add_person(self):
        name = self.input.text().strip()
        if name and name not in self.people:
            self.people.append(name)
            self.profiles[name] = list(ALL_ROLES)
            self.list_widget.addItem(name)
            self.input.clear()
            self.search.clear()
            self.update_count()
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def edit_person(self):
        row = self.list_widget.currentRow()
        name = self.input.text().strip()
        if row >= 0 and name:
            old_name = self.list_widget.item(row).text()
            source_index = self.people.index(old_name)
            self.people[source_index] = name
            self.profiles[name] = self.profiles.pop(old_name, list(ALL_ROLES))
            self.list_widget.item(row).setText(name)

    def delete_person(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            name = self.list_widget.item(row).text()
            self.people.remove(name)
            self.profiles.pop(name, None)
            self.list_widget.takeItem(row)
            self.update_count()

    def select_person(self, name):
        self.input.setText(name)
        self._loading_roles = True
        selected = set(self.profiles.get(name, ALL_ROLES))
        for role, check in self.role_checks.items():
            check.setChecked(role in selected)
            check.setEnabled(bool(name))
        self._loading_roles = False

    def update_selected_roles(self, *_args):
        if self._loading_roles:
            return
        name = self.list_widget.currentItem().text() if self.list_widget.currentItem() else ""
        if name:
            self.profiles[name] = [role for role, check in self.role_checks.items() if check.isChecked()]

    def set_selected_roles(self, roles):
        self._loading_roles = True
        selected = set(roles)
        for role, check in self.role_checks.items():
            check.setChecked(role in selected)
        self._loading_roles = False
        self.update_selected_roles()
