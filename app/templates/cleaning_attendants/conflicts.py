from collections import defaultdict
from datetime import date


ROLE_LABELS = {
    "cleaning_person": "sprzątanie sali",
    "console_person": "konsola Zoom",
    "microphone_1": "mikrofon 1",
    "microphone_2": "mikrofon 2",
    "lobby_attendant": "porządkowy hol",
    "hall_attendant": "porządkowy sala",
}


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _valid_person(value: str) -> bool:
    return bool(str(value).strip()) and str(value).strip() != "-"


def find_conflicts(project: dict) -> list[dict]:
    """Return people assigned to multiple duties on the same meeting date."""
    duties_by_date: dict[date, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    meeting_dates: set[date] = set()

    for assignment in project.get("attendant_assignments", []):
        duty_date = parse_date(assignment.get("date", ""))
        if not duty_date:
            continue
        meeting_dates.add(duty_date)
        for key in ("lobby_attendant", "hall_attendant"):
            person = str(assignment.get(key, "")).strip()
            if _valid_person(person):
                duties_by_date[duty_date][person].append(ROLE_LABELS[key])

    for assignment in project.get("weekly_assignments", []):
        start = parse_date(assignment.get("start_date", ""))
        end = parse_date(assignment.get("end_date", ""))
        if not start or not end:
            continue
        if start > end:
            start, end = end, start
        for duty_date in meeting_dates:
            if start <= duty_date <= end:
                for key in ("cleaning_person", "console_person", "microphone_1", "microphone_2"):
                    person = str(assignment.get(key, "")).strip()
                    if _valid_person(person):
                        duties_by_date[duty_date][person].append(ROLE_LABELS[key])

    conflicts = []
    for duty_date, people in sorted(duties_by_date.items()):
        for person, roles in sorted(people.items()):
            if len(roles) > 1:
                conflicts.append({"date": duty_date.isoformat(), "person": person, "roles": roles})
    return conflicts
