import re

from app.templates.field_service_groups.default_project import ROLE_LEADER


ROMAN_NUMBERS = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
}


def normalize_group_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    text = re.sub(r"^grupa\s+", "", text).strip()
    if text.isdigit():
        return str(int(text))
    roman = ROMAN_NUMBERS.get(text.upper())
    return str(roman) if roman else text


def group_leaders_from_project(project: dict) -> tuple[dict[str, str], list[str]]:
    leaders = {}
    names = []
    if project.get("template_id") != "field_service_groups":
        return leaders, names
    for group in project.get("groups", []):
        name = str(group.get("name", "")).strip()
        if not name:
            continue
        names.append(name)
        leader = next(
            (
                str(member.get("name", "")).strip()
                for member in group.get("members", [])
                if member.get("role") == ROLE_LEADER and str(member.get("name", "")).strip()
            ),
            "",
        )
        if leader:
            leaders[normalize_group_name(name)] = leader
    return leaders, names


def latest_group_leaders(entries: list[dict]) -> tuple[dict[str, str], list[str]]:
    for entry in entries:
        project = entry.get("project", {})
        if project.get("template_id") == "field_service_groups":
            return group_leaders_from_project(project)
    return {}, []
