import copy
from pathlib import Path

from app.config import FIELD_SERVICE_GROUPS_FILE
from app.core.project_io import ProjectIO


class GroupPlanStore:
    def __init__(self, path: Path = FIELD_SERVICE_GROUPS_FILE):
        self.path = Path(path)

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            project = ProjectIO.load_project(self.path)
        except ValueError:
            return None
        if project.get("template_id") != "field_service_groups":
            return None
        return project

    def save(self, project: dict):
        if project.get("template_id") != "field_service_groups":
            return
        ProjectIO.save_project(self.path, copy.deepcopy(project))

    def migrate_from_archive(self, entries: list[dict]) -> bool:
        if self.load() is not None:
            return False
        for entry in entries:
            project = entry.get("project", {})
            if project.get("template_id") == "field_service_groups":
                self.save(project)
                return True
        return False
