from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)


class PeopleDialog(QDialog):
    def __init__(self, people: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteka osób")
        self.resize(560, 640)
        self.people = list(people)

        layout = QVBoxLayout(self)
        title = QLabel("Biblioteka osób")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Jedna lista nazwisk używana przez wszystkie generatory.")
        subtitle.setObjectName("screenSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Szukaj osoby…")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.addItems(self.people)
        layout.addWidget(self.list_widget)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Imię i nazwisko")
        layout.addWidget(self.input)
        row = QHBoxLayout()
        add = QPushButton("Dodaj osobę")
        add.setObjectName("primaryButton")
        edit = QPushButton("Zmień")
        delete = QPushButton("Usuń")
        delete.setObjectName("dangerButton")
        for widget in (add, edit, delete):
            row.addWidget(widget)
        layout.addLayout(row)

        count = QLabel()
        count.setObjectName("screenSubtitle")
        count.setAlignment(Qt.AlignRight)
        layout.addWidget(count)
        self.count = count

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        self.search.textChanged.connect(self.filter_people)
        add.clicked.connect(self.add_person)
        edit.clicked.connect(self.edit_person)
        delete.clicked.connect(self.delete_person)
        self.list_widget.currentTextChanged.connect(self.input.setText)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
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
            self.list_widget.addItem(name)
            self.input.clear()
            self.search.clear()
            self.update_count()

    def edit_person(self):
        row = self.list_widget.currentRow()
        name = self.input.text().strip()
        if row >= 0 and name:
            old_name = self.list_widget.item(row).text()
            source_index = self.people.index(old_name)
            self.people[source_index] = name
            self.list_widget.item(row).setText(name)

    def delete_person(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            name = self.list_widget.item(row).text()
            self.people.remove(name)
            self.list_widget.takeItem(row)
            self.update_count()
