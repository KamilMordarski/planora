import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.app_info import APP_AUTHOR, APP_NAME, APP_TAGLINE, APP_VERSION


def version_tuple(version: str) -> tuple[int, int, int, int]:
    numbers = []
    for part in version.split("."):
        digits = "".join(character for character in part if character.isdigit())
        numbers.append(int(digits or 0))
    return tuple((numbers + [0, 0, 0, 0])[:4])


def render_version_info(version: str = APP_VERSION) -> str:
    numeric_version = version_tuple(version)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric_version},
    prodvers={numeric_version},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '041504B0',
        [
          StringStruct('CompanyName', '{APP_AUTHOR}'),
          StringStruct('FileDescription', '{APP_NAME} - {APP_TAGLINE}'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', '{APP_NAME}'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 {APP_AUTHOR}'),
          StringStruct('OriginalFilename', '{APP_NAME}.exe'),
          StringStruct('ProductName', '{APP_NAME}'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1045, 1200])])
  ]
)
"""


def main():
    parser = argparse.ArgumentParser(description="Generuje zasób wersji Windows dla Planory.")
    parser.add_argument("--output", default="windows-version-info.txt", help="Ścieżka pliku wynikowego")
    args = parser.parse_args()
    output = Path(args.output)
    output.write_text(render_version_info(), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
