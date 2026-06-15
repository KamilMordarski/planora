import shutil
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
from app.core.project_archive import project_display_title
from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry
from app.gui.responsive import ResponsiveActionBar


def _available_path(directory: Path, filename: str) -> Path:
    target = directory / filename
    number = 2
    while target.exists():
        target = directory / f"{Path(filename).stem}-{number}{Path(filename).suffix}"
        number += 1
    return target


class ProjectTransferDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import i eksport grafików")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        title = QLabel("Import i eksport grafików")
        title.setObjectName("screenTitle")
        info = QLabel(
            "Importuj edytowalne projekty JSON do lokalnej biblioteki albo wyeksportuj zaznaczone grafiki "
            "do wybranego folderu. PDF i JPG pozostają gotowymi dokumentami, a nie projektami do dalszej edycji."
        )
        info.setObjectName("screenSubtitle")
        info.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(info)

        self.projects = QListWidget()
        self.projects.setAlternatingRowColors(True)
        layout.addWidget(self.projects, 1)

        import_button = QPushButton("Importuj projekty JSON")
        export_button = QPushButton("Eksportuj zaznaczone")
        select_all = QPushButton("Zaznacz wszystkie")
        select_none = QPushButton("Odznacz wszystkie")
        import_button.setObjectName("primaryButton")
        import_button.clicked.connect(self.import_projects)
        export_button.clicked.connect(self.export_projects)
        select_all.clicked.connect(lambda: self._set_checks(Qt.Checked))
        select_none.clicked.connect(lambda: self._set_checks(Qt.Unchecked))
        layout.addWidget(ResponsiveActionBar([import_button, export_button, select_all, select_none], 150, 4))

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.reload()

    def reload(self):
        self.projects.clear()
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(PROJECTS_DIR.glob("*.json"), key=lambda item: item.name.casefold()):
            try:
                project = ProjectIO.load_project(path)
                template = TemplateRegistry.for_project(project)
                if not template:
                    continue
            except ValueError:
                continue
            item = QListWidgetItem(f"{project_display_title(project)}\n{path.name}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            self.projects.addItem(item)

    def import_projects(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Importuj grafiki Planory",
            str(Path.home()),
            "Projekty Planora JSON (*.json)",
        )
        imported = 0
        errors = []
        for value in paths:
            source = Path(value)
            try:
                project = ProjectIO.load_project(source)
                if not TemplateRegistry.for_project(project):
                    raise ValueError(f"Brak szablonu o ID: {project.get('template_id')}")
                destination = _available_path(PROJECTS_DIR, source.name)
                ProjectIO.save_project(destination, project)
                imported += 1
            except (OSError, ValueError) as exc:
                errors.append(f"{source.name}: {exc}")
        self.reload()
        if errors:
            QMessageBox.warning(self, "Nie zaimportowano części plików", "\n".join(errors))
        if imported:
            QMessageBox.information(self, "Import zakończony", f"Zaimportowano projektów: {imported}.")

    def export_projects(self):
        selected = [
            Path(self.projects.item(index).data(Qt.UserRole))
            for index in range(self.projects.count())
            if self.projects.item(index).checkState() == Qt.Checked
        ]
        if not selected:
            QMessageBox.information(self, "Wybierz grafiki", "Zaznacz co najmniej jeden projekt do eksportu.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Wybierz folder eksportu", str(Path.home()))
        if not directory:
            return
        destination_dir = Path(directory)
        exported = 0
        try:
            for source in selected:
                shutil.copy2(source, _available_path(destination_dir, source.name))
                exported += 1
        except OSError as exc:
            QMessageBox.warning(self, "Nie można wyeksportować grafików", str(exc))
            return
        QMessageBox.information(self, "Eksport zakończony", f"Wyeksportowano projektów: {exported}.")

    def _set_checks(self, state):
        for index in range(self.projects.count()):
            self.projects.item(index).setCheckState(state)
