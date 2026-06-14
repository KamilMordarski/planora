import html
import re
from datetime import date
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.templates.midweek_meeting.default_project import program_item, section


MEETINGS_URL = "https://wol.jw.org/pl/wol/meetings/r12/lp-p/{year}/{week}"
SECTION_PRESETS = {
    "SKARBY ZE SŁOWA BOŻEGO": "#666666",
    "ULEPSZAJMY SWOJĄ SŁUŻBĘ": "#e58b00",
    "CHRZEŚCIJAŃSKI TRYB ŻYCIA": "#c90000",
}


class WolImportError(RuntimeError):
    pass


def current_week_url(today: date | None = None) -> str:
    value = today or date.today()
    iso = value.isocalendar()
    return MEETINGS_URL.format(year=iso.year, week=iso.week)


def _download(url: str) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pl-PL,pl;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace"), response.geturl()
    except OSError as exc:
        raise WolImportError(f"Nie udało się pobrać programu: {exc}") from exc


def _plain_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _resolve_program_page(source: str, base_url: str) -> tuple[str, str]:
    if "/wol/meetings/" not in base_url:
        return source, base_url
    candidates = re.findall(r'href="([^"]*/wol/d/r12/lp-p/\d+[^"]*)"', source)
    if not candidates:
        raise WolImportError("Nie znaleziono programu „Życie i służba” na stronie wybranego tygodnia.")
    return _download(urljoin(base_url, candidates[0]))


def parse_wol_program(source: str) -> dict:
    heading_matches = list(re.finditer(r"(?is)<h([23])\b[^>]*>(.*?)</h\1>", source))
    if not heading_matches:
        raise WolImportError("Strona nie zawiera rozpoznawalnego programu zebrania.")

    result = {"bible_reading": "", "sections": []}
    current_section = None
    started = False
    for index, match in enumerate(heading_matches):
        level = match.group(1)
        heading = _plain_text(match.group(2))
        normalized = heading.upper()
        if level == "2" and normalized in SECTION_PRESETS:
            current_section = section(normalized, SECTION_PRESETS[normalized])
            result["sections"].append(current_section)
            started = True
            continue
        if level == "2" and not started and heading:
            result["bible_reading"] = heading
            continue
        point = re.match(r"^\d+\.\s*(.+)$", heading)
        if level != "3" or not point or current_section is None:
            continue
        next_start = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(source)
        following_text = _plain_text(source[match.end():next_start])
        duration = re.search(r"\((\d+\s*min)\)", following_text, re.IGNORECASE)
        title = point.group(1).strip()
        if duration:
            title = f"{title} ({duration.group(1)})"
        current_section["items"].append(program_item("", title))

    if not result["sections"] or not any(value["items"] for value in result["sections"]):
        raise WolImportError("Nie udało się rozpoznać punktów programu na stronie.")
    return result


def fetch_wol_program(url: str | None = None) -> dict:
    source, resolved_url = _download(url or current_week_url())
    source, resolved_url = _resolve_program_page(source, resolved_url)
    result = parse_wol_program(source)
    result["source_url"] = resolved_url
    return result


def standard_program_sections() -> list[dict]:
    return [
        section(
            "SKARBY ZE SŁOWA BOŻEGO",
            "#666666",
            [
                program_item("", "Przemówienie"),
                program_item("", "Wyszukujemy duchowe skarby"),
                program_item("", "Czytanie Biblii"),
            ],
        ),
        section(
            "ULEPSZAJMY SWOJĄ SŁUŻBĘ",
            "#e58b00",
            [
                program_item("", "Rozpoczynanie rozmowy"),
                program_item("", "Podtrzymywanie zainteresowania"),
                program_item("", "Pozyskiwanie uczniów"),
            ],
        ),
        section(
            "CHRZEŚCIJAŃSKI TRYB ŻYCIA",
            "#c90000",
            [
                program_item("", "Potrzeby zboru"),
                program_item("", "Zborowe studium Biblii"),
            ],
        ),
    ]
