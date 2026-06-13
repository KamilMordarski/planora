import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.app_info import APP_VERSION


def main():
    parser = argparse.ArgumentParser(description="Przygotuj update.json dla aktualizacji Planory przez GitHub.")
    parser.add_argument("--repo", required=True, help="Repozytorium w formacie LOGIN/NAZWA_REPO")
    parser.add_argument("--version", default=APP_VERSION, help=f"Numer wersji, domyślnie {APP_VERSION}")
    parser.add_argument("--branch", default="main", help="Gałąź zawierająca update.json")
    parser.add_argument("--note", action="append", default=[], help="Notatka wydania; opcję można podać wiele razy")
    args = parser.parse_args()

    release_tag = args.version if str(args.version).startswith("v") else f"v{args.version}"
    release_url = f"https://github.com/{args.repo}/releases/download/{release_tag}"
    payload = {
        "latest_version": args.version,
        "release_date": date.today().isoformat(),
        "download_url": f"{release_url}/Planora-Windows.zip",
        "download_urls": {
            "windows": f"{release_url}/Planora-Windows.zip",
            "macos": f"{release_url}/Planora-macOS.zip",
        },
        "notes": args.note or ["Nowa wersja Planory jest dostępna do pobrania."],
    }
    output = Path("update.json")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    raw_url = f"https://raw.githubusercontent.com/{args.repo}/{args.branch}/update.json"
    print(f"Zapisano: {output.resolve()}")
    print(f"Stały adres aktualizacji Planory:\n{raw_url}")


if __name__ == "__main__":
    main()
