import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from app.config import UPDATE_URL
from app.core.app_info import APP_VERSION


class UpdateCheckError(RuntimeError):
    pass


class UpdateDownloadError(RuntimeError):
    pass


class UpdateDownloadCancelled(RuntimeError):
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
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise UpdateCheckError(f"Nie udało się sprawdzić aktualizacji: {exc}") from exc

        if not isinstance(payload, dict) or not payload.get("latest_version"):
            raise UpdateCheckError("Serwer aktualizacji zwrócił nieprawidłowe dane.")
        self._update_info = payload
        return self.compare_versions(str(payload["latest_version"])) > 0

    def get_update_info(self) -> dict[str, Any] | None:
        return self._update_info

    @staticmethod
    def _platform_key() -> str:
        if sys.platform.startswith("win"):
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        return "linux"

    def get_download_url(self, platform: str | None = None) -> str:
        info = self._update_info or {}
        platform_urls = info.get("download_urls", {})
        if isinstance(platform_urls, dict):
            platform_url = platform_urls.get(platform or self._platform_key())
            if platform_url:
                return str(platform_url)
        return str(info.get("download_url", ""))

    def get_manual_download_url(self, platform: str | None = None) -> str:
        info = self._update_info or {}
        platform_key = platform or self._platform_key()
        platform_urls = info.get("download_urls", {})
        if isinstance(platform_urls, dict):
            for key in (f"{platform_key}_exe", f"{platform_key}_manual", f"{platform_key}_installer"):
                platform_url = platform_urls.get(key)
                if platform_url:
                    return str(platform_url)
        for key in ("manual_download_url", "direct_download_url"):
            if info.get(key):
                return str(info[key])
        return ""

    @staticmethod
    def _filename_from_url(url: str, fallback: str) -> str:
        filename = Path(unquote(urlparse(url).path)).name
        return filename or fallback

    def suggested_filename(self, platform: str | None = None) -> str:
        platform_key = platform or self._platform_key()
        return self._filename_from_url(self.get_download_url(platform), f"Planora-{platform_key}.zip")

    def suggested_manual_filename(self, platform: str | None = None) -> str:
        platform_key = platform or self._platform_key()
        return self._filename_from_url(
            self.get_manual_download_url(platform),
            self.suggested_filename(platform) or f"Planora-{platform_key}",
        )

    def download_update(self, destination: Path, progress_callback=None, url: str | None = None) -> Path:
        url = url or self.get_download_url()
        if not url:
            raise UpdateDownloadError("Brak bezpośredniego adresu pobierania tej aktualizacji.")

        destination = Path(destination)
        partial = destination.with_name(f"{destination.name}.part")
        last_error = None
        for attempt in range(1, 4):
            request = Request(
                url,
                headers={
                    "User-Agent": "Planora-Updater",
                    "Accept": "application/octet-stream, application/zip, */*",
                },
            )
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with urlopen(request, timeout=90) as response, partial.open("wb") as output:
                    total = int(response.headers.get("Content-Length", 0) or 0)
                    downloaded = 0
                    while True:
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and progress_callback(downloaded, total) is False:
                            raise UpdateDownloadCancelled("Pobieranie aktualizacji zostało anulowane.")
                partial.replace(destination)
                return destination
            except UpdateDownloadCancelled:
                partial.unlink(missing_ok=True)
                raise
            except Exception as exc:
                partial.unlink(missing_ok=True)
                last_error = exc
                if attempt == 3:
                    break
        raise UpdateDownloadError(f"Nie udało się pobrać aktualizacji: {last_error}") from last_error
