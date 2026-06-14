import os
import sys
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
ASSETS_DIR = PACKAGE_DIR / "assets"
APP_ICON = ASSETS_DIR / "icons" / "app_icon.png"
STARTUP_SOUND = ASSETS_DIR / "sounds" / "opening-glider.mp3"
LEGACY_DATA_DIR = PROJECT_ROOT / "data"

UPDATE_URL = "https://raw.githubusercontent.com/KamilMordarski/planora/main/update.json"
DATA_DIR_OVERRIDE = os.environ.get("PLANORA_DATA_DIR") or os.environ.get("GENERATOR_GRAFIKOW_DATA_DIR")


def _platform_data_dir(app_dir_name: str) -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / app_dir_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_dir_name
    slug = app_dir_name.casefold().replace(" ", "-")
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / slug


def _user_data_dir() -> Path:
    if DATA_DIR_OVERRIDE:
        return Path(DATA_DIR_OVERRIDE).expanduser()
    return _platform_data_dir("Planora")


def _legacy_user_data_dir() -> Path:
    if DATA_DIR_OVERRIDE:
        return Path(DATA_DIR_OVERRIDE).expanduser()
    if sys.platform == "win32":
        return _platform_data_dir("GeneratorGrafikow")
    if sys.platform == "darwin":
        return _platform_data_dir("Generator Grafikow")
    return _platform_data_dir("generator-grafikow")


USER_DATA_DIR = _user_data_dir()
LEGACY_USER_DATA_DIR = _legacy_user_data_dir()
PEOPLE_FILE = USER_DATA_DIR / "people.json"
PEOPLE_ROLES_FILE = USER_DATA_DIR / "people-roles.json"
SETTINGS_FILE = USER_DATA_DIR / "settings.json"
UPDATE_DIR = USER_DATA_DIR / "updates"
UPDATE_RESULT_FILE = USER_DATA_DIR / "update-result.json"
AUTOSAVE_FILE = USER_DATA_DIR / "autosave-project.json"
PROJECT_ARCHIVE_DIR = USER_DATA_DIR / "project-archive"
