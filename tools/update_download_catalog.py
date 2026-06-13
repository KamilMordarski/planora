import argparse
from pathlib import Path


DOWNLOADS_DIR = Path("downloads")


def version_key(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return (0,)


def version_readme(repo: str, version: str) -> str:
    release_url = f"https://github.com/{repo}/releases/download/v{version}"
    return f"""# Planora {version}

## Windows

- [Pobierz gotowy plik EXE]({release_url}/Planora-{version}.exe)
- [Pobierz paczkę ZIP dla aktualizatora]({release_url}/Planora-Windows.zip)

## macOS

- [Pobierz paczkę aplikacji]({release_url}/Planora-macOS.zip)

[Zobacz informacje o wydaniu](https://github.com/{repo}/releases/tag/v{version})
"""


def latest_readme(repo: str, version: str) -> str:
    latest_url = f"https://github.com/{repo}/releases/latest/download"
    return f"""# Najnowsza Planora

Aktualna wersja: **{version}**

## Windows

- [Pobierz Planora-latest.exe]({latest_url}/Planora-latest.exe)
- [Pobierz paczkę ZIP dla aktualizatora]({latest_url}/Planora-Windows.zip)

## macOS

- [Pobierz paczkę aplikacji]({latest_url}/Planora-macOS.zip)

[Zobacz najnowsze wydanie](https://github.com/{repo}/releases/latest)
"""


def root_readme(repo: str, versions: list[str]) -> str:
    version_links = "\n".join(f"- [{version}]({version}/)" for version in versions)
    return f"""# Pobieranie Planory

- [Pobierz najnowszą wersję](latest/)

## Starsze wersje

{version_links}

Pliki wykonywalne i paczki są przechowywane w
[GitHub Releases](https://github.com/{repo}/releases), aby nie powiększać
niepotrzebnie repozytorium.
"""


def update_catalog(repo: str, version: str, downloads_dir: Path = DOWNLOADS_DIR):
    version = version.removeprefix("v")
    (downloads_dir / version).mkdir(parents=True, exist_ok=True)
    (downloads_dir / "latest").mkdir(parents=True, exist_ok=True)
    (downloads_dir / version / "README.md").write_text(version_readme(repo, version), encoding="utf-8")
    (downloads_dir / "latest" / "README.md").write_text(latest_readme(repo, version), encoding="utf-8")

    versions = sorted(
        (path.name for path in downloads_dir.iterdir() if path.is_dir() and path.name != "latest"),
        key=version_key,
        reverse=True,
    )
    (downloads_dir / "README.md").write_text(root_readme(repo, versions), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Aktualizuje katalog pobierania Planory.")
    parser.add_argument("--repo", required=True, help="Repozytorium w formacie właściciel/nazwa")
    parser.add_argument("--version", required=True, help="Numer publikowanej wersji")
    args = parser.parse_args()
    update_catalog(args.repo, args.version)


if __name__ == "__main__":
    main()
