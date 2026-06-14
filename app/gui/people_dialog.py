from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import USER_DATA_DIR
from app.core.people_roles import (
    ALL_PERMISSIONS,
    ASSIGNMENT_OPTIONS,
    PERSON_ROLE_OPTIONS,
    normalize_profile,
    normalize_profiles,
)
from app.core.project_io import ProjectIO
from app.gui.responsive import ResponsiveActionBar


class PeopleDialog(QDialog):
    def __init__(self, people: list[str], profiles: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteka osób")
        self.resize(920, 680)
        self.people = list(people)
        self.profiles = normalize_profiles(self.people, profiles)
        self.permission_checks: dict[str, QCheckBox] = {}
        self.person_role_checks: dict[str, QCheckBox] = {}
        self._loading_roles = False

        layout = QVBoxLayout(self)
        title = QLabel("Biblioteka osób")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Jedna lista nazwisk, ról zborowych i możliwych przydziałów używana w całej aplikacji.")
        subtitle.setObjectName("screenSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.splitter = QSplitter(Qt.Horizontal)
        splitter = self.splitter
        people_panel = QWidget()
        people_layout = QVBoxLayout(people_panel)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Szukaj osoby…")
        self.search.setClearButtonEnabled(True)
        people_layout.addWidget(self.search)

        filters = QVBoxLayout()
        self.role_filter = QComboBox()
        self.role_filter.addItem("Wszystkie role", "")
        for role, label in PERSON_ROLE_OPTIONS.items():
            self.role_filter.addItem(label, role)
        self.permission_filter = QComboBox()
        self.permission_filter.addItem("Wszystkie możliwe przydziały", "")
        for permission, label in ASSIGNMENT_OPTIONS.items():
            self.permission_filter.addItem(label, permission)
        filters.addWidget(QLabel("Filtr roli:"))
        filters.addWidget(self.role_filter)
        filters.addWidget(QLabel("Filtr możliwego przydziału:"))
        filters.addWidget(self.permission_filter)
        people_layout.addLayout(filters)

        import_json = QPushButton("Importuj listę JSON")
        import_json.setToolTip("Dodaje osoby oraz odtwarza ich role i możliwe przydziały bez usuwania obecnej listy.")
        export_json = QPushButton("Eksportuj listę JSON")
        export_json.setToolTip("Zapisuje nazwiska, role i możliwe przydziały w jednym pliku JSON.")
        people_layout.addWidget(ResponsiveActionBar([import_json, export_json], 150, 2))

        self.list_widget = QListWidget()
        self.list_widget.setSpacing(3)
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

        roles_group = QGroupBox("Role i możliwe przydziały wybranej osoby")
        roles_layout = QVBoxLayout(roles_group)
        roles_help = QLabel(
            "Role opisują funkcję osoby w zborze. Możliwe przydziały sterują podpowiedziami w generatorach. "
            "Pionier pomocniczy jest automatycznie zdejmowany po wskazanej dacie."
        )
        roles_help.setObjectName("helpText")
        roles_help.setWordWrap(True)
        roles_layout.addWidget(roles_help)
        all_permissions = QPushButton("Zaznacz wszystkie przydziały")
        no_permissions = QPushButton("Wyczyść przydziały")
        roles_layout.addWidget(ResponsiveActionBar([all_permissions, no_permissions], 180, 2))
        roles_scroll = QScrollArea()
        roles_scroll.setWidgetResizable(True)
        roles_content = QWidget()
        roles_content_layout = QVBoxLayout(roles_content)
        person_roles_group = QGroupBox("Role osoby")
        person_roles_form = QVBoxLayout(person_roles_group)
        for role, label in PERSON_ROLE_OPTIONS.items():
            check = QCheckBox(label)
            check.toggled.connect(self.update_selected_roles)
            self.person_role_checks[role] = check
            person_roles_form.addWidget(check)
        auxiliary_form = QFormLayout()
        self.auxiliary_until = QDateEdit()
        self.auxiliary_until.setCalendarPopup(True)
        self.auxiliary_until.setDisplayFormat("dd.MM.yyyy")
        self.auxiliary_until.setDate(QDate.currentDate().addMonths(1))
        self.auxiliary_until.dateChanged.connect(self.update_selected_roles)
        auxiliary_form.addRow("Pionier pomocniczy do:", self.auxiliary_until)
        person_roles_form.addLayout(auxiliary_form)
        roles_content_layout.addWidget(person_roles_group)

        permissions_group = QGroupBox("Możliwe przydziały")
        permissions_layout = QVBoxLayout(permissions_group)
        for permission, label in ASSIGNMENT_OPTIONS.items():
            check = QCheckBox(label)
            check.toggled.connect(self.update_selected_roles)
            self.permission_checks[permission] = check
            permissions_layout.addWidget(check)
        roles_content_layout.addWidget(permissions_group)
        roles_content_layout.addStretch()
        roles_scroll.setWidget(roles_content)
        roles_layout.addWidget(roles_scroll, 1)
        splitter.addWidget(roles_group)
        splitter.setSizes([430, 470])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        self.search.textChanged.connect(self.filter_people)
        self.role_filter.currentIndexChanged.connect(self.filter_people)
        self.permission_filter.currentIndexChanged.connect(self.filter_people)
        import_json.clicked.connect(self.import_json)
        export_json.clicked.connect(self.export_json)
        add.clicked.connect(self.add_person)
        edit.clicked.connect(self.edit_person)
        delete.clicked.connect(self.delete_person)
        self.list_widget.currentItemChanged.connect(self.select_person)
        all_permissions.clicked.connect(lambda: self.set_selected_permissions(ALL_PERMISSIONS))
        no_permissions.clicked.connect(lambda: self.set_selected_permissions(()))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.refresh_list()
        if self.people:
            self.list_widget.setCurrentRow(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        orientation = Qt.Vertical if self.width() < 900 else Qt.Horizontal
        if self.splitter.orientation() != orientation:
            self.splitter.setOrientation(orientation)
            self.splitter.setSizes([300, 430] if orientation == Qt.Vertical else [430, 470])

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
            f"Dodano nowych osób: {added}\nZaktualizowano profile: {roles_updated}\n"
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
            f"Zapisano osoby wraz z rolami i możliwymi przydziałami:\n{destination}",
        )

    def refresh_list(self):
        current_name = self._item_name(self.list_widget.currentItem())
        self.list_widget.clear()
        for person in self.people:
            self.list_widget.addItem(self._person_item(person))
        self.filter_people()
        if current_name:
            for index in range(self.list_widget.count()):
                if self._item_name(self.list_widget.item(index)) == current_name:
                    self.list_widget.setCurrentRow(index)
                    break

    def _person_item(self, name: str) -> QListWidgetItem:
        profile = normalize_profile(self.profiles.get(name))
        labels = [PERSON_ROLE_OPTIONS[role] for role in profile["roles"] if role in PERSON_ROLE_OPTIONS]
        text = name if not labels else f"{name}\n  Role: {' · '.join(labels)}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, name)
        if labels:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setToolTip("Role: " + ", ".join(labels))
        else:
            item.setToolTip("Brak przypisanych ról")
        return item

    @staticmethod
    def _item_name(item) -> str:
        return str(item.data(Qt.UserRole)) if item else ""

    def update_count(self):
        visible = sum(not self.list_widget.item(index).isHidden() for index in range(self.list_widget.count()))
        self.count.setText(f"Wyświetlono: {visible} z {len(self.people)}")

    def filter_people(self, *_args):
        phrase = self.search.text().casefold().strip()
        selected_role = self.role_filter.currentData()
        selected_permission = self.permission_filter.currentData()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            name = self._item_name(item)
            profile = normalize_profile(self.profiles.get(name))
            searchable = " ".join(
                [
                    name,
                    *(PERSON_ROLE_OPTIONS.get(role, role) for role in profile["roles"]),
                    *(ASSIGNMENT_OPTIONS.get(permission, permission) for permission in profile["permissions"]),
                ]
            ).casefold()
            item.setHidden(
                bool(phrase and phrase not in searchable)
                or bool(selected_role and selected_role not in profile["roles"])
                or bool(selected_permission and selected_permission not in profile["permissions"])
            )
        self.update_count()

    def add_person(self):
        name = self.input.text().strip()
        if name and name not in self.people:
            self.people.append(name)
            self.profiles[name] = normalize_profile()
            self.input.clear()
            self.search.clear()
            self.refresh_list()
            for index in range(self.list_widget.count()):
                if self._item_name(self.list_widget.item(index)) == name:
                    self.list_widget.setCurrentRow(index)
                    break

    def edit_person(self):
        row = self.list_widget.currentRow()
        name = self.input.text().strip()
        if row >= 0 and name:
            old_name = self._item_name(self.list_widget.item(row))
            if name != old_name and name in self.people:
                QMessageBox.information(self, "Osoba już istnieje", "W bibliotece jest już osoba o tej nazwie.")
                return
            source_index = self.people.index(old_name)
            self.people[source_index] = name
            self.profiles[name] = self.profiles.pop(old_name, normalize_profile())
            self.refresh_list()

    def delete_person(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            name = self._item_name(self.list_widget.item(row))
            self.people.remove(name)
            self.profiles.pop(name, None)
            self.list_widget.takeItem(row)
            self.filter_people()

    def select_person(self, current, _previous=None):
        name = self._item_name(current)
        self.input.setText(name)
        self._loading_roles = True
        profile = normalize_profile(self.profiles.get(name))
        selected_permissions = set(profile["permissions"])
        selected_roles = set(profile["roles"])
        for permission, check in self.permission_checks.items():
            check.setChecked(permission in selected_permissions)
            check.setEnabled(bool(name))
        for role, check in self.person_role_checks.items():
            check.setChecked(role in selected_roles)
            check.setEnabled(bool(name))
        auxiliary_date = QDate.fromString(profile["auxiliary_pioneer_until"], "yyyy-MM-dd")
        self.auxiliary_until.setDate(auxiliary_date if auxiliary_date.isValid() else QDate.currentDate().addMonths(1))
        self.auxiliary_until.setEnabled(bool(name) and "auxiliary_pioneer" in selected_roles)
        self._loading_roles = False

    def update_selected_roles(self, *_args):
        if self._loading_roles:
            return
        current_item = self.list_widget.currentItem()
        name = self._item_name(current_item)
        if name:
            selected_roles = [role for role, check in self.person_role_checks.items() if check.isChecked()]
            self.auxiliary_until.setEnabled("auxiliary_pioneer" in selected_roles)
            self.profiles[name] = normalize_profile(
                {
                    "permissions": [
                        permission for permission, check in self.permission_checks.items() if check.isChecked()
                    ],
                    "roles": selected_roles,
                    "auxiliary_pioneer_until": (
                        self.auxiliary_until.date().toString("yyyy-MM-dd")
                        if "auxiliary_pioneer" in selected_roles
                        else ""
                    ),
                }
            )
            row = self.list_widget.row(current_item)
            self.list_widget.takeItem(row)
            self.list_widget.insertItem(row, self._person_item(name))
            self.list_widget.setCurrentRow(row)
            self.filter_people()

    def set_selected_permissions(self, permissions):
        self._loading_roles = True
        selected = set(permissions)
        for permission, check in self.permission_checks.items():
            check.setChecked(permission in selected)
        self._loading_roles = False
        self.update_selected_roles()
