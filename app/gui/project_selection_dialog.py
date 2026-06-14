from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.config import PROJECTS_DIR
from app.core.project_archive import ProjectArchive
from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry
from app.gui.responsive import ResponsiveActionBar


class ProjectSelectionDialog(QDialog):
    def __init__(
        self,
        purpose: str,
        current_project: dict | None = None,
        current_path: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Wybierz projekty")
        self.resize(720, 520)
        self._known_ids = set()

        layout = QVBoxLayout(self)
        title = QLabel(f"Wybierz projekty do {purpose}")
        title.setObjectName("screenTitle")
        info = QLabel(
            "Analizowane będą wyłącznie zaznaczone projekty. Kopie awaryjne i inne zapisane pliki "
            "nie są dodawane automatycznie."
        )
        info.setObjectName("screenSubtitle")
        info.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(info)

        self.projects = QListWidget()
        self.projects.setAlternatingRowColors(True)
        layout.addWidget(self.projects, 1)

        add_files = QPushButton("Dodaj zapisane projekty JSON")
        remove = QPushButton("Usuń z wyboru")
        select_all = QPushButton("Zaznacz wszystkie")
        select_none = QPushButton("Odznacz wszystkie")
        add_files.setObjectName("primaryButton")
        add_files.clicked.connect(self.add_files)
        remove.clicked.connect(self.remove_selected)
        select_all.clicked.connect(lambda: self._set_checks(Qt.Checked))
        select_none.clicked.connect(lambda: self._set_checks(Qt.Unchecked))
        layout.addWidget(ResponsiveActionBar([add_files, remove, select_all, select_none], 150, 4))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Otwórz z wybranymi")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if current_project:
            self._add_project(current_project, current_path, "Aktualnie otwarty projekt")

    def _add_project(self, project: dict, source_path: Path | None = None, prefix: str = ""):
        if not TemplateRegistry.for_project(project):
            raise ValueError(f"Brak szablonu o ID: {project.get('template_id')}")
        entry = ProjectArchive.entry_for_project(project, source_path)
        if entry["archive_id"] in self._known_ids:
            return
        self._known_ids.add(entry["archive_id"])
        label = entry["title"]
        if prefix:
            label = f"{prefix}: {label}"
        if source_path:
            label += f"\n{source_path}"
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setData(Qt.UserRole, entry)
        item.setToolTip(str(source_path or "Projekt działa obecnie w edytorze"))
        self.projects.addItem(item)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Wybierz projekty do sprawdzenia",
            str(PROJECTS_DIR),
            "Projekty Planora JSON (*.json)",
        )
        errors = []
        for value in paths:
            path = Path(value)
            try:
                self._add_project(ProjectIO.load_project(path), path)
            except ValueError as exc:
                errors.append(f"{path.name}: {exc}")
        if errors:
            QMessageBox.warning(self, "Nie można dodać części projektów", "\n".join(errors))

    def remove_selected(self):
        for item in self.projects.selectedItems():
            entry = item.data(Qt.UserRole) or {}
            self._known_ids.discard(entry.get("archive_id", ""))
            self.projects.takeItem(self.projects.row(item))

    def _set_checks(self, state):
        for index in range(self.projects.count()):
            self.projects.item(index).setCheckState(state)

    def selected_entries(self) -> list[dict]:
        return [
            self.projects.item(index).data(Qt.UserRole)
            for index in range(self.projects.count())
            if self.projects.item(index).checkState() == Qt.Checked
        ]

    def accept(self):
        if not self.selected_entries():
            QMessageBox.information(self, "Wybierz projekty", "Zaznacz co najmniej jeden projekt do sprawdzenia.")
            return
        super().accept()
