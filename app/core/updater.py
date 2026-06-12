import json
import re
from typing import Any
from urllib.request import Request, urlopen

from app.config import UPDATE_URL
from app.core.app_info import APP_VERSION


class UpdateCheckError(RuntimeError):
    pass


class UpdateChecker:
    def __init__(self, update_url: str = UPDATE_URL, current_version: str = APP_VERSION):
        self.update_url = update_url
        self.current_version = current_version
        self._update_info: dict[str, Any] | None = None

    @staticmethod
    def _version_parts(version: str) -> tuple[int, ...]:
        parts = re.findall(r"\d+", str(version))
        return tuple(int(part) for part in parts) or (0,)

    def compare_versions(self, remote_version: str, local_version: str | None = None) -> int:
        remote = self._version_parts(remote_version)
        local = self._version_parts(local_version or self.current_version)
        size = max(len(remote), len(local))
        remote += (0,) * (size - len(remote))
        local += (0,) * (size - len(local))
        return (remote > local) - (remote < local)

    def check_for_updates(self) -> bool:
        if not self.update_url:
            raise UpdateCheckError("Najpierw ustaw adres update.json w ustawieniach aplikacji.")
        request = Request(self.update_url, headers={"User-Agent": "Planora-Updater"})
        try:
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise UpdateCheckError(f"Nie udało się sprawdzić aktualizacji: {exc}") from exc

        if not isinstance(payload, dict) or not payload.get("latest_version"):
            raise UpdateCheckError("Serwer aktualizacji zwrócił nieprawidłowe dane.")
        self._update_info = payload
        return self.compare_versions(str(payload["latest_version"])) > 0

    def get_update_info(self) -> dict[str, Any] | None:
        return self._update_info
