from collections import defaultdict

from app.core.assignment_tools import extract_assignments


def _issue(message: str, severity: str = "warning") -> dict:
    return {"severity": severity, "message": message}


def _schedule_rows(project: dict) -> list[dict]:
    rows = []
    for key in ("weeks", "meetings", "weekly_assignments", "attendant_assignments"):
        rows.extend(value for value in project.get(key, []) if isinstance(value, dict))
    return rows


def validate_project(project: dict) -> list[dict]:
    issues = []
    template_id = project.get("template_id", "")
    rows = _schedule_rows(project)
    assignments = extract_assignments(project)

    if template_id == "field_service_groups":
        groups = project.get("groups", [])
        if not groups:
            issues.append(_issue("Plan nie zawiera żadnej grupy.", "error"))
        if not any(group.get("members") for group in groups):
            issues.append(_issue("W grupach nie przypisano jeszcze żadnej osoby."))
        return issues

    if not rows:
        issues.append(_issue("Projekt nie zawiera jeszcze żadnego terminu.", "error"))
        return issues

    for index, row in enumerate(rows, start=1):
        if not str(row.get("date") or row.get("start_date") or "").strip():
            issues.append(_issue(f"Termin {index} nie ma daty."))

    if not assignments:
        issues.append(_issue("Nie przypisano jeszcze żadnej osoby."))

    if template_id == "service_meetings":
        for index, row in enumerate(project.get("meetings", []), start=1):
            if not str(row.get("conductor", "")).strip():
                issues.append(_issue(f"Zbiórka {index} nie ma prowadzącego."))
    elif template_id == "public_talk_watchtower":
        required = {
            "chairman": "przewodniczącego",
            "lecturer": "mówcy",
            "watchtower_conductor": "prowadzącego Strażnicę",
            "reader": "lektora",
        }
        for index, row in enumerate(project.get("weeks", []), start=1):
            if row.get("type") == "special":
                continue
            for key, label in required.items():
                if not str(row.get(key, "")).strip():
                    issues.append(_issue(f"Tydzień {index} nie ma {label}."))
    elif template_id == "cleaning_attendants":
        from app.templates.cleaning_attendants.conflicts import find_conflicts

        required_weekly = {
            "cleaning_person": "osoby sprzątającej",
            "console_person": "osoby przy konsoli",
            "microphone_1": "pierwszej osoby do mikrofonu",
            "microphone_2": "drugiej osoby do mikrofonu",
        }
        for index, row in enumerate(project.get("weekly_assignments", []), start=1):
            for key, label in required_weekly.items():
                if not str(row.get(key, "")).strip():
                    issues.append(_issue(f"Tydzień sprzątania {index} nie ma {label}."))
        for index, row in enumerate(project.get("attendant_assignments", []), start=1):
            if not str(row.get("lobby_attendant", "")).strip():
                issues.append(_issue(f"Dyżur porządkowych {index} nie ma osoby na holu."))
            if not str(row.get("hall_attendant", "")).strip():
                issues.append(_issue(f"Dyżur porządkowych {index} nie ma osoby na sali."))
        for conflict in find_conflicts(project):
            issues.append(
                _issue(
                    f"{conflict['person']} ma kolizję w dniu {conflict['date']}: "
                    f"{', '.join(conflict['roles'])}."
                )
            )
    elif template_id == "midweek_meeting":
        for index, row in enumerate(project.get("meetings", []), start=1):
            if row.get("type") != "special" and not str(row.get("chairman", "")).strip():
                issues.append(_issue(f"Zebranie {index} nie ma przewodniczącego."))

    duties_by_person_and_date = defaultdict(list)
    for assignment in assignments:
        date_value = str(assignment.get("date", "")).strip()
        if date_value:
            key = (assignment["person"].casefold(), date_value)
            duties_by_person_and_date[key].append(assignment["role"])
    for (_person_key, date_value), roles in duties_by_person_and_date.items():
        if len(roles) > 1:
            person = next(
                assignment["person"]
                for assignment in assignments
                if assignment["person"].casefold() == _person_key and assignment["date"] == date_value
            )
            issues.append(_issue(f"{person} ma {len(roles)} obowiązki w dniu {date_value}: {', '.join(roles)}."))
    return issues
