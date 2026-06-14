from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.core.people_roles import eligible_people
from app.templates.service_meetings.default_project import meeting_row


POLISH_WEEKDAYS = {
    0: "Poniedziałek",
    1: "Wtorek",
    2: "Środa",
    3: "Czwartek",
    4: "Piątek",
    5: "Sobota",
    6: "Niedziela",
}
POLISH_MONTHS = {
    1: "stycznia",
    2: "lutego",
    3: "marca",
    4: "kwietnia",
    5: "maja",
    6: "czerwca",
    7: "lipca",
    8: "sierpnia",
    9: "września",
    10: "października",
    11: "listopada",
    12: "grudnia",
}


def parse_date(value) -> date | None:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        pass
    for date_format in ("%d.%m.%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def generate_recurring_dates(start: date, end: date, weekdays: set[int]) -> list[date]:
    if start > end:
        start, end = end, start
    result = []
    current = start
    while current <= end:
        if current.weekday() in weekdays:
            result.append(current)
        current += timedelta(days=1)
    return result


def display_date(value: date) -> str:
    return f"{POLISH_WEEKDAYS[value.weekday()]} {value.day} {POLISH_MONTHS[value.month]} {value.year}"


def iso_or_text_date(value) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else str(value or "")


def extract_assignments(project: dict) -> list[dict]:
    template_id = project.get("template_id", "")
    assignments = []

    def add(duty_date, person, role, details=""):
        if str(person or "").strip():
            assignments.append(
                {
                    "date": iso_or_text_date(duty_date),
                    "person": str(person).strip(),
                    "role": role,
                    "details": str(details or "").strip(),
                    "template_id": template_id,
                }
            )

    if template_id == "service_meetings":
        for row in project.get("meetings", []):
            add(row.get("date"), row.get("conductor"), "Prowadzenie zbiórki", row.get("place"))
    elif template_id == "cleaning_attendants":
        for row in project.get("weekly_assignments", []):
            duty_date = row.get("start_date")
            add(duty_date, row.get("cleaning_person"), "Sprzątanie sali", row.get("group"))
            add(duty_date, row.get("console_person"), "Konsola / Zoom")
            add(duty_date, row.get("microphone_1"), "Mikrofon")
            add(duty_date, row.get("microphone_2"), "Mikrofon")
        for row in project.get("attendant_assignments", []):
            add(row.get("date"), row.get("lobby_attendant"), "Porządkowy hol")
            add(row.get("date"), row.get("hall_attendant"), "Porządkowy sala")
    elif template_id == "public_talk_watchtower":
        for row in project.get("weeks", []):
            duty_date = row.get("date")
            add(duty_date, row.get("chairman"), "Przewodniczący")
            add(duty_date, row.get("lecturer"), "Wykład publiczny", row.get("lecture_topic"))
            add(duty_date, row.get("watchtower_conductor"), "Prowadzący Strażnicę")
            add(duty_date, row.get("reader"), "Lektor")
    elif template_id == "midweek_meeting":
        for meeting in project.get("meetings", []):
            duty_date = meeting.get("date")
            add(duty_date, meeting.get("chairman"), "Przewodniczący")
            add(duty_date, meeting.get("opening_prayer"), "Modlitwa początkowa")
            add(duty_date, meeting.get("closing_prayer"), "Modlitwa końcowa")
            for section in meeting.get("sections", []):
                for item in section.get("items", []):
                    add(duty_date, item.get("participant_1"), item.get("role_1") or item.get("title"))
                    add(duty_date, item.get("participant_2"), item.get("role_2") or item.get("title"))
    return assignments


def person_assignments(project: dict, person: str) -> list[dict]:
    target = person.casefold().strip()
    return [item for item in extract_assignments(project) if item["person"].casefold() == target]


def archive_assignments(entries: list[dict]) -> list[dict]:
    result = []
    for entry in entries:
        for assignment in extract_assignments(entry.get("project", {})):
            enriched = dict(assignment)
            enriched["archive_id"] = entry.get("archive_id", "")
            enriched["project_title"] = entry.get("title") or entry.get("template_name") or assignment["template_id"]
            result.append(enriched)
    return result


def assignment_rows_for_person(assignments: list[dict], person: str) -> list[dict]:
    target = person.casefold().strip()
    return [item for item in assignments if item.get("person", "").casefold() == target]


def assigned_people_by_date(project: dict | None) -> dict[str, set[str]]:
    result = defaultdict(set)
    for item in extract_assignments(project or {}):
        result[item["date"]].add(item["person"].casefold())
    return dict(result)


def export_person_assignments(path: Path, project: dict, person: str):
    export_assignment_rows_text(path, person_assignments(project, person), person)


def export_assignment_rows_text(path: Path, rows: list[dict], person: str = ""):
    heading = f"Przydziały: {person}" if person else "Przydziały"
    rows = sorted(rows, key=lambda item: (iso_or_text_date(item.get("date")), item.get("role", "")))
    lines = [heading, ""]
    for row in rows:
        suffix = f" — {row['details']}" if row.get("details") else ""
        project = f" [{row['project_title']}]" if row.get("project_title") else ""
        lines.append(f"{row['date']} — {row['role']}{suffix}{project}")
    if not rows:
        lines.append("Brak przydziałów.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ics_escape(value) -> str:
    return str(value or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def export_ics(path: Path, project: dict, person: str = ""):
    assignments = person_assignments(project, person) if person else extract_assignments(project)
    export_assignment_rows_ics(path, assignments)


def export_assignment_rows_ics(path: Path, assignments: list[dict]):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Planora//PL", "CALSCALE:GREGORIAN"]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for index, item in enumerate(assignments):
        parsed = parse_date(item["date"])
        if not parsed:
            continue
        day = parsed.strftime("%Y%m%d")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:planora-{day}-{index}@local",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{day}",
                f"SUMMARY:{_ics_escape(item['role'])}",
                f"DESCRIPTION:{_ics_escape(item['person'] + (' — ' + item['details'] if item.get('details') else '') + (' [' + item['project_title'] + ']' if item.get('project_title') else ''))}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    Path(path).write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def shift_project_dates(project: dict, days: int) -> int:
    changed = 0

    def shift(container, key):
        nonlocal changed
        parsed = parse_date(container.get(key))
        if parsed:
            container[key] = (parsed + timedelta(days=days)).isoformat()
            changed += 1

    for key in ("meetings", "weeks", "weekly_assignments", "attendant_assignments"):
        for row in project.get(key, []):
            shift(row, "date")
            shift(row, "start_date")
            shift(row, "end_date")
    return changed


def build_service_meetings_plan(
    project: dict,
    dates: list[date],
    people: list[str],
    profiles: dict,
    time: str,
    place: str,
    balance_assignments: bool = True,
    avoid_consecutive: bool = True,
    blocked_people_by_date: dict[str, set[str]] | None = None,
) -> list[dict]:
    candidates = eligible_people(people, profiles, "service_conductor")
    if not candidates:
        return []
    counts = Counter(item.get("conductor") for item in project.get("meetings", []) if item.get("conductor"))
    previous = ""
    rows = []
    for index, duty_date in enumerate(dates):
        blocked = (blocked_people_by_date or {}).get(duty_date.isoformat(), set())
        available = [person for person in candidates if person.casefold() not in blocked]
        if not available:
            rows.append(meeting_row(duty_date.isoformat(), time, place, ""))
            continue
        if avoid_consecutive and len(candidates) > 1:
            without_previous = [person for person in available if person != previous]
            if without_previous:
                available = without_previous
        if balance_assignments:
            selected = min(available, key=lambda person: (counts[person], person.casefold()))
        else:
            selected = available[index % len(available)]
        counts[selected] += 1
        previous = selected
        rows.append(meeting_row(duty_date.isoformat(), time, place, selected))
    return rows
