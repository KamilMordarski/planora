import html
import re
from datetime import date
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.templates.midweek_meeting.default_project import normal_meeting, program_item, section


JW_MEETINGS_BASE_URL = "https://wol.jw.org/pl/wol/meetings/r12/lp-p/"
MEETINGS_URL = JW_MEETINGS_BASE_URL + "{year}/{week}"
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


def meeting_date_from_url(
    url: str,
    today: date | None = None,
    iso_weekday: int = 3,
) -> str:
    iso_weekday = max(1, min(7, int(iso_weekday)))
    match = re.search(r"/(\d{4})/(\d{1,2})(?:[/?#]|$)", str(url))
    if match:
        try:
            return date.fromisocalendar(
                int(match.group(1)),
                int(match.group(2)),
                iso_weekday,
            ).isoformat()
        except ValueError:
            pass
    value = today or date.today()
    iso = value.isocalendar()
    return date.fromisocalendar(iso.year, iso.week, iso_weekday).isoformat()


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
        raise WolImportError("Nie znaleziono programu „Życie i służba” na stronie wybranego tygodnia JW.")
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


def fetch_wol_program(url: str | None = None, meeting_weekday: int = 3) -> dict:
    requested_url = url or current_week_url()
    source, resolved_url = _download(requested_url)
    source, resolved_url = _resolve_program_page(source, resolved_url)
    result = parse_wol_program(source)
    result["source_url"] = resolved_url
    result["meeting_date"] = meeting_date_from_url(
        requested_url,
        iso_weekday=meeting_weekday,
    )
    return result


def append_imported_meeting(project: dict, imported: dict) -> dict:
    meeting = normal_meeting(imported.get("meeting_date", ""))
    meeting["bible_reading"] = imported.get("bible_reading", "")
    meeting["sections"] = imported.get("sections", [])
    project.setdefault("meetings", []).append(meeting)
    return meeting


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
