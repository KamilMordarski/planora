import json
import shutil
from pathlib import Path
from typing import Any

from app.config import (
    AUTOSAVE_FILE,
    LEGACY_USER_DATA_DIR,
    PEOPLE_FILE,
    PEOPLE_ROLES_FILE,
    PROJECTS_DIR,
    RECOVERY_DIR,
    SETTINGS_FILE,
    UPDATE_URL,
    USER_DATA_DIR,
)
from app.core.people_roles import normalize_profiles


DEFAULT_PEOPLE = []

DEFAULT_SETTINGS = {
    "update_url": UPDATE_URL,
    "check_updates_on_start": False,
    "theme": "ocean",
    "font_scale": 100,
    "interface_density": "comfortable",
    "corner_style": "rounded",
    "animations_enabled": True,
    "animation_speed": 100,
    "startup_splash_enabled": True,
    "sounds_enabled": True,
    "hover_sounds_enabled": False,
    "sound_volume": 35,
}


class ProjectIO:
    @staticmethod
    def ensure_user_data():
        if (
            not USER_DATA_DIR.exists()
            and LEGACY_USER_DATA_DIR.exists()
            and LEGACY_USER_DATA_DIR.resolve() != USER_DATA_DIR.resolve()
        ):
            try:
                shutil.copytree(LEGACY_USER_DATA_DIR, USER_DATA_DIR)
            except OSError:
                pass
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        legacy_autosave = USER_DATA_DIR / "autosave-project.json"
        if legacy_autosave.exists() and not AUTOSAVE_FILE.exists():
            try:
                legacy_autosave.replace(AUTOSAVE_FILE)
            except OSError:
                pass
        if not PEOPLE_FILE.exists():
            ProjectIO._write_json(PEOPLE_FILE, DEFAULT_PEOPLE)
        if not SETTINGS_FILE.exists():
            ProjectIO._write_json(SETTINGS_FILE, DEFAULT_SETTINGS)

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"Plik nie istnieje: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Nie można odczytać pliku JSON: {path}") from exc

    @staticmethod
    def _write_json(path: Path, value: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def load_project(path: Path) -> dict:
        project = ProjectIO._read_json(path)
        if not isinstance(project, dict):
            raise ValueError("Wybrany plik nie zawiera prawidłowego projektu grafiku.")
        if "template_id" not in project:
            if not isinstance(project.get("weeks"), list):
                raise ValueError("Nie można rozpoznać typu wybranego projektu.")
            project["template_id"] = "public_talk_watchtower"
        return project

    @staticmethod
    def save_project(path: Path, project: dict):
        ProjectIO._write_json(path, project)

    @staticmethod
    def load_people() -> list[str]:
        ProjectIO.ensure_user_data()
        try:
            value = ProjectIO._read_json(PEOPLE_FILE)
        except ValueError:
            value = list(DEFAULT_PEOPLE)
            ProjectIO.save_people(value)
        if not isinstance(value, list):
            value = list(DEFAULT_PEOPLE)
            ProjectIO.save_people(value)
        return [str(person) for person in value]

    @staticmethod
    def save_people(people: list[str]):
        ProjectIO._write_json(PEOPLE_FILE, people)

    @staticmethod
    def load_people_profiles(people: list[str] | None = None) -> dict[str, dict]:
        people = list(people if people is not None else ProjectIO.load_people())
        try:
            value = ProjectIO._read_json(PEOPLE_ROLES_FILE)
        except ValueError:
            value = {}
        profiles = normalize_profiles(people, value)
        ProjectIO.save_people_profiles(profiles)
        return profiles

    @staticmethod
    def save_people_profiles(profiles: dict[str, dict]):
        ProjectIO._write_json(PEOPLE_ROLES_FILE, profiles)

    @staticmethod
    def import_people(path: Path, current_people: list[str] | None = None) -> tuple[list[str], int]:
        people, _profiles, added, _roles_updated = ProjectIO.import_people_library(path, current_people)
        return people, added

    @staticmethod
    def import_people_library(
        path: Path,
        current_people: list[str] | None = None,
        current_profiles: dict[str, dict] | None = None,
    ) -> tuple[list[str], dict[str, dict], int, int]:
        payload = ProjectIO._read_json(path)
        imported_profiles = {}
        value = payload
        if isinstance(payload, dict):
            value = payload.get("people")
            profiles_value = payload.get("profiles", {})
            if isinstance(profiles_value, dict):
                imported_profiles.update(profiles_value)
        if not isinstance(value, list):
            raise ValueError('Lista osób musi być tablicą JSON albo obiektem z polem "people".')

        imported_names = []
        for person in value:
            if isinstance(person, dict):
                name = str(person.get("name", "")).strip()
                if name:
                    imported_names.append(name)
                    imported_profiles[name] = person
            else:
                name = str(person).strip()
                if name:
                    imported_names.append(name)

        people = [str(person).strip() for person in (current_people or []) if str(person).strip()]
        known = {person.casefold() for person in people}
        added = 0
        for name in imported_names:
            if name and name.casefold() not in known:
                people.append(name)
                known.add(name.casefold())
                added += 1
        profiles = normalize_profiles(people, current_profiles)
        roles_updated = 0
        for imported_name, profile in imported_profiles.items():
            existing_name = next((name for name in people if name.casefold() == str(imported_name).casefold()), "")
            if not existing_name:
                continue
            normalized = normalize_profiles([existing_name], {existing_name: profile})[existing_name]
            if profiles.get(existing_name) != normalized:
                roles_updated += 1
            profiles[existing_name] = normalized
        return people, profiles, added, roles_updated

    @staticmethod
    def export_people_library(path: Path, people: list[str], profiles: dict[str, dict]):
        normalized = normalize_profiles(people, profiles)
        payload = {
            "format": "planora_people_library",
            "version": 2,
            "people": [
                {
                    "name": person,
                    **normalized.get(person, {}),
                }
                for person in people
            ],
        }
        ProjectIO._write_json(path, payload)

    @staticmethod
    def load_settings() -> dict:
        ProjectIO.ensure_user_data()
        try:
            value = ProjectIO._read_json(SETTINGS_FILE)
        except ValueError:
            value = {}
        settings = dict(DEFAULT_SETTINGS)
        if isinstance(value, dict):
            settings.update(value)
        settings.pop("accent_color", None)
        settings["update_url"] = UPDATE_URL
        ProjectIO.save_settings(settings)
        return settings

    @staticmethod
    def save_settings(settings: dict):
        saved = dict(settings)
        saved.pop("accent_color", None)
        ProjectIO._write_json(SETTINGS_FILE, saved)
