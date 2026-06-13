import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from app.config import UPDATE_RESULT_FILE


class UpdateInstallError(RuntimeError):
    pass


def _independent_process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return environment


def is_install_supported() -> bool:
    return bool(getattr(sys, "frozen", False)) and (sys.platform.startswith("win") or sys.platform == "darwin")


def current_install_target() -> Path:
    executable = Path(sys.executable).resolve()
    if sys.platform.startswith("win"):
        return executable
    if sys.platform == "darwin":
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent
    raise UpdateInstallError("Automatyczna instalacja nie jest dostępna dla tego uruchomienia Planory.")


def validate_update_archive(archive: Path, platform: str | None = None):
    archive = Path(archive)
    platform = platform or ("windows" if sys.platform.startswith("win") else "macos")
    expected = "Planora.exe" if platform == "windows" else "Planora.app/"
    try:
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            if package.testzip():
                raise UpdateInstallError("Pobrana paczka aktualizacji jest uszkodzona.")
    except (OSError, zipfile.BadZipFile) as exc:
        raise UpdateInstallError(f"Nie można odczytać paczki aktualizacji: {exc}") from exc

    if platform == "windows" and "Planora.exe" not in names:
        raise UpdateInstallError("Paczka aktualizacji nie zawiera pliku Planora.exe.")
    if platform == "macos" and not any(name.startswith(expected) for name in names):
        raise UpdateInstallError("Paczka aktualizacji nie zawiera aplikacji Planora.app.")


def launch_update_installer(archive: Path, version: str = ""):
    if not is_install_supported():
        raise UpdateInstallError("Automatyczna instalacja działa w gotowej wersji Planory dla Windows i macOS.")

    archive = Path(archive).resolve()
    validate_update_archive(archive)
    target = current_install_target()
    try:
        helper_dir = Path(tempfile.mkdtemp(prefix="planora-updater-"))
        helper = helper_dir / ("Planora-Updater.exe" if sys.platform.startswith("win") else "Planora-Updater")
        shutil.copy2(sys.executable, helper)
        if sys.platform == "darwin":
            helper.chmod(helper.stat().st_mode | 0o111)

        command = [
            str(helper),
            "--apply-update",
            str(archive),
            "--target",
            str(target),
            "--parent-pid",
            str(os.getpid()),
            "--result-file",
            str(UPDATE_RESULT_FILE),
            "--version",
            version,
        ]
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
            "cwd": str(helper_dir),
            "env": _independent_process_environment(),
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(command, **kwargs)
    except OSError as exc:
        raise UpdateInstallError(f"Nie udało się uruchomić instalatora aktualizacji: {exc}") from exc


def run_update_installer_from_args(arguments: list[str]) -> int | None:
    if "--apply-update" not in arguments:
        return None

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--apply-update", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--result-file", required=True)
    parser.add_argument("--version", default="")
    args = parser.parse_args(arguments)

    archive = Path(args.apply_update)
    target = Path(args.target)
    result_file = Path(args.result_file)
    backup = None
    try:
        backup = apply_update(archive, target, args.parent_pid, keep_backup=True)
        _write_result(result_file, True, f"Planora {args.version or 'w nowej wersji'} została zainstalowana.")
        _launch_installed_app(target)
    except Exception as exc:
        if backup and backup.exists():
            _remove_path(target)
            backup.replace(target)
        _write_result(result_file, False, f"Nie udało się zainstalować aktualizacji: {exc}")
        if target.exists():
            try:
                _launch_installed_app(target)
            except OSError:
                pass
        return 1
    if backup:
        try:
            _remove_path(backup)
        except OSError:
            pass
    try:
        archive.unlink(missing_ok=True)
    except OSError:
        pass
    return 0


def apply_update(
    archive: Path,
    target: Path,
    parent_pid: int,
    platform: str | None = None,
    keep_backup: bool = False,
) -> Path | None:
    validate_update_archive(archive, platform)
    _wait_for_process_exit(parent_pid)
    with tempfile.TemporaryDirectory(prefix="planora-update-stage-") as directory:
        stage = Path(directory)
        payload = _extract_payload(archive, stage, platform)
        return _replace_installation(payload, target, keep_backup)


def _wait_for_process_exit(pid: int, timeout_seconds: int = 120):
    if sys.platform.startswith("win"):
        import ctypes

        synchronize = 0x00100000
        process = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if process:
            try:
                result = ctypes.windll.kernel32.WaitForSingleObject(process, timeout_seconds * 1000)
                if result == 0x00000102:
                    raise UpdateInstallError("Planora nie zamknęła się przed upływem limitu czasu.")
            finally:
                ctypes.windll.kernel32.CloseHandle(process)
        return

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        time.sleep(0.2)
    raise UpdateInstallError("Planora nie zamknęła się przed upływem limitu czasu.")


def _extract_payload(archive: Path, stage: Path, platform: str | None = None) -> Path:
    platform = platform or ("windows" if sys.platform.startswith("win") else "macos")
    if platform == "macos":
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(stage)], check=True)
        payload = stage / "Planora.app"
    else:
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                destination = (stage / member.filename).resolve()
                if not destination.is_relative_to(stage.resolve()):
                    raise UpdateInstallError("Paczka aktualizacji zawiera niebezpieczną ścieżkę.")
            package.extractall(stage)
        payload = stage / "Planora.exe"

    if not payload.exists():
        raise UpdateInstallError("Nie znaleziono aplikacji w pobranej paczce.")
    return payload


def cleanup_stale_update_helpers(max_age_seconds: int = 6 * 60 * 60):
    temp_root = Path(tempfile.gettempdir()).resolve()
    cutoff = time.time() - max_age_seconds
    for candidate in temp_root.glob("planora-updater-*"):
        try:
            resolved = candidate.resolve()
            if resolved.parent != temp_root or candidate.stat().st_mtime > cutoff:
                continue
            shutil.rmtree(candidate, ignore_errors=True)
        except OSError:
            continue


def _replace_installation(payload: Path, target: Path, keep_backup: bool = False) -> Path | None:
    backup = target.with_name(f"{target.name}.previous")
    _remove_path(backup)
    if backup.exists():
        raise UpdateInstallError("Nie można usunąć starej kopii zapasowej aplikacji.")
    moved_to_backup = False
    try:
        target.replace(backup)
        moved_to_backup = True
        if payload.is_dir():
            shutil.copytree(payload, target, symlinks=True)
        else:
            shutil.copy2(payload, target)
    except Exception:
        if moved_to_backup:
            _remove_path(target)
            backup.replace(target)
        raise
    if keep_backup:
        return backup
    _remove_path(backup)
    return None


def _remove_path(path: Path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _launch_installed_app(target: Path):
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "cwd": str(target.parent),
        "env": _independent_process_environment(),
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        process = subprocess.Popen([str(target)], **kwargs)
        try:
            exit_code = process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            return
        raise OSError(f"Nowa wersja Planory zakończyła działanie podczas uruchamiania (kod {exit_code}).")
    elif sys.platform == "darwin":
        kwargs["start_new_session"] = True
        subprocess.Popen(["/usr/bin/open", "-n", str(target)], **kwargs)


def _write_result(path: Path, success: bool, message: str):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"success": success, "message": message}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def consume_update_result(path: Path = UPDATE_RESULT_FILE) -> dict | None:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    path.unlink(missing_ok=True)
    return result if isinstance(result, dict) else None
