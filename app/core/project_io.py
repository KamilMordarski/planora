import json
import shutil
from pathlib import Path
from typing import Any

from app.config import LEGACY_DATA_DIR, LEGACY_USER_DATA_DIR, PEOPLE_FILE, SETTINGS_FILE, UPDATE_URL, USER_DATA_DIR


DEFAULT_PEOPLE = [
    "Łukasz Kapusta",
    "Sebastian Skiba",
    "Denis Kurdyk",
    "Paweł Ugolik",
    "Paweł Sawaryn",
    "Richie Fisayo",
    "Sławomir Mordarski",
    "Adrian Pokojowczyk jr.",
    "Jerzy Godzisz",
    "Paweł Poczęsny",
    "Andrzej Szmit",
    "Mirosław Różycki",
    "Dominik Janus",
]

DEFAULT_SETTINGS = {
    "update_url": UPDATE_URL,
    "check_updates_on_start": False,
    "theme": "ocean",
    "accent_color": "",
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
        if not PEOPLE_FILE.exists():
            legacy_people = LEGACY_DATA_DIR / "people.json"
            if legacy_people.exists():
                shutil.copy2(legacy_people, PEOPLE_FILE)
            else:
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
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

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
    def import_people(path: Path, current_people: list[str] | None = None) -> tuple[list[str], int]:
        value = ProjectIO._read_json(path)
        if isinstance(value, dict):
            value = value.get("people")
        if not isinstance(value, list):
            raise ValueError(
                'Lista osób musi być tablicą JSON albo obiektem z polem "people".'
            )

        people = [str(person).strip() for person in (current_people or []) if str(person).strip()]
        known = {person.casefold() for person in people}
        added = 0
        for person in value:
            name = str(person).strip()
            if name and name.casefold() not in known:
                people.append(name)
                known.add(name.casefold())
                added += 1
        return people, added

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
        settings["update_url"] = UPDATE_URL
        ProjectIO.save_settings(settings)
        return settings

    @staticmethod
    def save_settings(settings: dict):
        ProjectIO._write_json(SETTINGS_FILE, settings)
