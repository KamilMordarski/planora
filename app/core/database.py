import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
LEGACY_MIGRATION_KEY = "legacy_json_migration_v1"
GROUP_PLAN_KEY = "field_service_groups"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


class LocalDatabase:
    """Local-only SQLite storage used for Planora's internal application data."""

    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA secure_delete = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA temp_store = MEMORY")
            connection.execute("PRAGMA trusted_schema = OFF")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
            self._restrict_permissions()

    def initialize(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    name_key TEXT NOT NULL UNIQUE,
                    position INTEGER NOT NULL,
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_archive (
                    archive_id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    project_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_people_position
                    ON people(position);
                CREATE INDEX IF NOT EXISTS idx_project_archive_updated_at
                    ON project_archive(updated_at DESC);
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _restrict_permissions(self):
        try:
            os.chmod(self.path.parent, 0o700)
            if self.path.exists():
                os.chmod(self.path, 0o600)
        except OSError:
            # Windows normally inherits the current user's AppData ACL.
            pass

    def metadata(self, key: str) -> str | None:
        self.initialize()
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_metadata(self, key: str, value: str, connection: sqlite3.Connection | None = None):
        statement = (
            "INSERT INTO metadata(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        )
        if connection is not None:
            connection.execute(statement, (key, value))
            return
        self.initialize()
        with self.connection() as active:
            active.execute(statement, (key, value))

    def load_settings(self) -> dict:
        self.initialize()
        with self.connection() as connection:
            row = connection.execute("SELECT payload FROM settings WHERE id = 1").fetchone()
        value = _json_load(row["payload"], {}) if row else {}
        return value if isinstance(value, dict) else {}

    def save_settings(self, settings: dict):
        self.initialize()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO settings(id, payload, updated_at) VALUES(1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (_json_dump(settings), _utc_now()),
            )

    def load_people(self) -> list[str]:
        self.initialize()
        with self.connection() as connection:
            rows = connection.execute("SELECT name FROM people ORDER BY position, id").fetchall()
        return [str(row["name"]) for row in rows]

    def load_people_profiles(self) -> dict[str, dict]:
        self.initialize()
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT name, profile_json FROM people ORDER BY position, id"
            ).fetchall()
        profiles = {}
        for row in rows:
            value = _json_load(row["profile_json"], {})
            profiles[str(row["name"])] = value if isinstance(value, dict) else {}
        return profiles

    def save_people(self, people: list[str]):
        self.initialize()
        clean_people = []
        known = set()
        for person in people:
            name = str(person).strip()
            key = name.casefold()
            if name and key not in known:
                clean_people.append(name)
                known.add(key)
        now = _utc_now()
        with self.connection() as connection:
            existing = {
                str(row["name_key"]): str(row["profile_json"])
                for row in connection.execute("SELECT name_key, profile_json FROM people")
            }
            connection.execute("DELETE FROM people")
            connection.executemany(
                """
                INSERT INTO people(name, name_key, position, profile_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                [
                    (name, name.casefold(), position, existing.get(name.casefold(), "{}"), now, now)
                    for position, name in enumerate(clean_people)
                ],
            )

    def save_people_profiles(self, profiles: dict[str, dict]):
        self.initialize()
        now = _utc_now()
        with self.connection() as connection:
            next_position = int(
                connection.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM people").fetchone()[0]
            )
            for name, profile in profiles.items():
                clean_name = str(name).strip()
                if not clean_name:
                    continue
                key = clean_name.casefold()
                row = connection.execute(
                    "SELECT id FROM people WHERE name_key = ?",
                    (key,),
                ).fetchone()
                if row:
                    connection.execute(
                        "UPDATE people SET profile_json = ?, updated_at = ? WHERE id = ?",
                        (_json_dump(profile), now, row["id"]),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO people(
                            name, name_key, position, profile_json, created_at, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        (clean_name, key, next_position, _json_dump(profile), now, now),
                    )
                    next_position += 1

    def save_people_library(self, people: list[str], profiles: dict[str, dict]):
        self.initialize()
        clean_people = []
        known = set()
        for person in people:
            name = str(person).strip()
            key = name.casefold()
            if name and key not in known:
                clean_people.append(name)
                known.add(key)
        now = _utc_now()
        with self.connection() as connection:
            connection.execute("DELETE FROM people")
            connection.executemany(
                """
                INSERT INTO people(name, name_key, position, profile_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        name,
                        name.casefold(),
                        position,
                        _json_dump(profiles.get(name, {})),
                        now,
                        now,
                    )
                    for position, name in enumerate(clean_people)
                ],
            )

    def load_document(self, key: str) -> dict | None:
        self.initialize()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM documents WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        value = _json_load(row["payload"], None)
        return value if isinstance(value, dict) else None

    def save_document(self, key: str, payload: dict):
        self.initialize()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO documents(key, payload, updated_at) VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (key, _json_dump(payload), _utc_now()),
            )

    def save_archive_entry(self, entry: dict):
        self.initialize()
        with self.connection() as connection:
            self._save_archive_entry(connection, entry)

    @staticmethod
    def _save_archive_entry(connection: sqlite3.Connection, entry: dict):
        connection.execute(
            """
            INSERT INTO project_archive(
                archive_id, template_id, template_name, title,
                updated_at, source_path, project_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(archive_id) DO UPDATE SET
                template_id = excluded.template_id,
                template_name = excluded.template_name,
                title = excluded.title,
                updated_at = excluded.updated_at,
                source_path = excluded.source_path,
                project_json = excluded.project_json
            """,
            (
                str(entry.get("archive_id", "")),
                str(entry.get("template_id", "")),
                str(entry.get("template_name", "")),
                str(entry.get("title", "")),
                str(entry.get("updated_at", "")),
                str(entry.get("source_path", "")),
                _json_dump(entry.get("project", {})),
            ),
        )

    def load_archive_entries(self) -> list[dict]:
        self.initialize()
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT archive_id, template_id, template_name, title,
                       updated_at, source_path, project_json
                FROM project_archive
                ORDER BY updated_at DESC
                """
            ).fetchall()
        entries = []
        for row in rows:
            project = _json_load(row["project_json"], None)
            if not isinstance(project, dict):
                continue
            entries.append(
                {
                    "archive_id": str(row["archive_id"]),
                    "template_id": str(row["template_id"]),
                    "template_name": str(row["template_name"]),
                    "title": str(row["title"]),
                    "updated_at": str(row["updated_at"]),
                    "source_path": str(row["source_path"]),
                    "project": project,
                }
            )
        return entries

    def delete_archive_entries(self, archive_ids: list[str]) -> int:
        if not archive_ids:
            return 0
        self.initialize()
        with self.connection() as connection:
            before = connection.total_changes
            connection.executemany(
                "DELETE FROM project_archive WHERE archive_id = ?",
                [(archive_id,) for archive_id in archive_ids],
            )
            return connection.total_changes - before

    def migrate_legacy_json(
        self,
        *,
        settings_path: Path,
        people_path: Path,
        profiles_path: Path,
        group_plan_path: Path,
        archive_directory: Path,
        backup_directory: Path,
    ) -> bool:
        self.initialize()
        if self.metadata(LEGACY_MIGRATION_KEY):
            return False

        settings = self._read_legacy_json(settings_path)
        people = self._read_legacy_json(people_path)
        profiles = self._read_legacy_json(profiles_path)
        group_plan = self._read_legacy_json(group_plan_path)
        archive_entries = []
        if archive_directory.exists():
            for path in archive_directory.glob("*.json"):
                entry = self._read_legacy_json(path)
                if isinstance(entry, dict) and isinstance(entry.get("project"), dict):
                    archive_entries.append(entry)

        with self.connection() as connection:
            if isinstance(settings, dict):
                connection.execute(
                    "INSERT OR IGNORE INTO settings(id, payload, updated_at) VALUES(1, ?, ?)",
                    (_json_dump(settings), _utc_now()),
                )

            existing_people = connection.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            if not existing_people and isinstance(people, list):
                profile_map = profiles if isinstance(profiles, dict) else {}
                profiles_by_key = {
                    str(name).casefold(): profile
                    for name, profile in profile_map.items()
                }
                now = _utc_now()
                clean_people = []
                known = set()
                for person in people:
                    name = str(person).strip()
                    key = name.casefold()
                    if name and key not in known:
                        clean_people.append(name)
                        known.add(key)
                connection.executemany(
                    """
                    INSERT INTO people(
                        name, name_key, position, profile_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            name,
                            name.casefold(),
                            position,
                            _json_dump(profiles_by_key.get(name.casefold(), {})),
                            now,
                            now,
                        )
                        for position, name in enumerate(clean_people)
                    ],
                )

            if isinstance(group_plan, dict):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO documents(key, payload, updated_at)
                    VALUES(?, ?, ?)
                    """,
                    (GROUP_PLAN_KEY, _json_dump(group_plan), _utc_now()),
                )

            for entry in archive_entries:
                if str(entry.get("archive_id", "")).strip():
                    self._save_archive_entry(connection, entry)

            self.set_metadata(LEGACY_MIGRATION_KEY, _utc_now(), connection)

        legacy_archive_paths = (
            list(archive_directory.glob("*.json")) if archive_directory.exists() else []
        )
        self._backup_legacy_files(
            [
                settings_path,
                people_path,
                profiles_path,
                group_plan_path,
                *legacy_archive_paths,
            ],
            backup_directory,
            archive_directory,
        )
        return True

    @staticmethod
    def _read_legacy_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _backup_legacy_files(paths: list[Path], backup_directory: Path, archive_directory: Path):
        for path in paths:
            if not path.exists():
                continue
            destination = (
                backup_directory / "project-archive" / path.name
                if path.parent == archive_directory
                else backup_directory / path.name
            )
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                path.unlink()
            except OSError:
                # Migration is already committed; leaving the original local file is safe.
                continue
