import copy
from pathlib import Path

from app.config import DATABASE_FILE, FIELD_SERVICE_GROUPS_FILE
from app.core.database import GROUP_PLAN_KEY, LocalDatabase


class GroupPlanStore:
    def __init__(
        self,
        path: Path | None = None,
        database: LocalDatabase | None = None,
    ):
        legacy_path = Path(path) if path is not None else FIELD_SERVICE_GROUPS_FILE
        database_path = (
            legacy_path.with_suffix(".db")
            if path is not None
            else DATABASE_FILE
        )
        self.database = database or LocalDatabase(database_path)

    def load(self) -> dict | None:
        project = self.database.load_document(GROUP_PLAN_KEY)
        if project is None:
            return None
        if project.get("template_id") != "field_service_groups":
            return None
        return project

    def save(self, project: dict):
        if project.get("template_id") != "field_service_groups":
            return
        self.database.save_document(GROUP_PLAN_KEY, copy.deepcopy(project))

    def migrate_from_archive(self, entries: list[dict]) -> bool:
        if self.load() is not None:
            return False
        for entry in entries:
            project = entry.get("project", {})
            if project.get("template_id") == "field_service_groups":
                self.save(project)
                return True
        return False
