import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.config import PROJECT_ARCHIVE_DIR
from app.core.assignment_tools import parse_date
from app.core.project_io import ProjectIO
from app.core.template_registry import TemplateRegistry


ARCHIVE_ID_KEY = "_planora_archive_id"
RETENTION_DAYS = 90


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def project_display_title(project: dict) -> str:
    template = TemplateRegistry.for_project(project)
    fallback = template.name if template else str(project.get("template_id", "Projekt"))
    base = fallback
    for key in ("document_title", "title", "congregation"):
        value = str(project.get(key, "")).strip()
        if value:
            base = value.replace("\n", " ")
            break
    period = str(project.get("period", "")).strip()
    if period:
        return f"{base} · {period}"
    dates = []
    for key in ("weeks", "meetings", "weekly_assignments", "attendant_assignments"):
        for row in project.get(key, []):
            if not isinstance(row, dict):
                continue
            parsed = parse_date(row.get("date") or row.get("start_date"))
            if parsed:
                dates.append(parsed)
    if dates:
        first, last = min(dates), max(dates)
        date_range = first.strftime("%d.%m.%Y")
        if last != first:
            date_range += f"–{last.strftime('%d.%m.%Y')}"
        return f"{base} · {date_range}"
    return base


class ProjectArchive:
    def __init__(self, directory: Path = PROJECT_ARCHIVE_DIR, retention_days: int = RETENTION_DAYS):
        self.directory = Path(directory)
        self.retention_days = retention_days

    @staticmethod
    def ensure_identity(project: dict, source_path: Path | None = None) -> str:
        archive_id = str(project.get(ARCHIVE_ID_KEY, "")).strip()
        if not archive_id:
            archive_id = (
                uuid5(NAMESPACE_URL, str(Path(source_path).resolve()).casefold()).hex
                if source_path
                else uuid4().hex
            )
            project[ARCHIVE_ID_KEY] = archive_id
        return archive_id

    def save(self, project: dict) -> dict:
        archive_id = self.ensure_identity(project)
        template = TemplateRegistry.for_project(project)
        entry = {
            "archive_id": archive_id,
            "template_id": project.get("template_id", ""),
            "template_name": template.name if template else project.get("template_id", ""),
            "title": project_display_title(project),
            "updated_at": _utc_now().isoformat(),
            "project": copy.deepcopy(project),
        }
        ProjectIO._write_json(self.directory / f"{archive_id}.json", entry)
        return entry

    def load_entries(self) -> list[dict]:
        if not self.directory.exists():
            return []
        entries = []
        for path in self.directory.glob("*.json"):
            try:
                entry = ProjectIO._read_json(path)
            except ValueError:
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("project"), dict):
                continue
            entries.append(entry)
        return sorted(entries, key=lambda item: str(item.get("updated_at", "")), reverse=True)

    def cleanup(self, now: datetime | None = None) -> int:
        if not self.directory.exists():
            return 0
        threshold = (now or _utc_now()).astimezone(UTC) - timedelta(days=self.retention_days)
        removed = 0
        for path in self.directory.glob("*.json"):
            try:
                entry = ProjectIO._read_json(path)
            except ValueError:
                continue
            updated_at = _parse_timestamp(entry.get("updated_at", "")) if isinstance(entry, dict) else None
            if updated_at and updated_at < threshold:
                path.unlink(missing_ok=True)
                removed += 1
        return removed
