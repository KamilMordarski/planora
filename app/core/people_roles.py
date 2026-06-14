from datetime import date


ASSIGNMENT_OPTIONS = {
    "service_conductor": "Prowadzenie zbiórki do służby",
    "console": "Obsługa konsoli / Zoom",
    "microphone": "Obsługa mikrofonu",
    "attendant": "Służba porządkowa",
    "cleaning": "Sprzątanie sali",
    "chairman": "Przewodniczenie zebraniu",
    "public_speaker": "Wykład publiczny",
    "watchtower_conductor": "Prowadzenie Studium Strażnicy",
    "reader": "Czytanie / lektor",
    "training_part": "Punkty ćwiczebne, w tym Czytanie Biblii",
    "midweek_other": "Zebranie w tygodniu — pozostałe punkty",
    "prayer": "Modlitwa na zebraniu",
}

PERSON_ROLE_OPTIONS = {
    "elder": "Starszy",
    "ministerial_servant": "Sługa pomocniczy",
    "special_pioneer": "Pionier specjalny",
    "regular_pioneer": "Pionier stały",
    "auxiliary_pioneer": "Pionier pomocniczy",
}

ALL_PERMISSIONS = tuple(ASSIGNMENT_OPTIONS)
ALL_PERSON_ROLES = tuple(PERSON_ROLE_OPTIONS)

# Compatibility aliases for older modules and exported integrations.
ROLE_OPTIONS = ASSIGNMENT_OPTIONS
ALL_ROLES = ALL_PERMISSIONS


def _migrate_permissions(values) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return list(ALL_PERMISSIONS)
    migrated = [value for value in values if value in ASSIGNMENT_OPTIONS]
    if "midweek_participant" in values:
        migrated.extend(("training_part", "midweek_other"))
    if "reader" in values and "training_part" not in migrated:
        migrated.append("training_part")
    return list(dict.fromkeys(migrated))


def _valid_until(value) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return ""


def normalize_profile(value=None, today: date | None = None) -> dict:
    current_date = today or date.today()
    if isinstance(value, (list, tuple)):
        permissions = _migrate_permissions(value)
        roles = []
        auxiliary_until = ""
    elif isinstance(value, dict):
        if "permissions" in value:
            permissions = _migrate_permissions(value.get("permissions"))
            roles_source = value.get("roles", value.get("person_roles", []))
        else:
            legacy_roles = value.get("roles", ALL_PERMISSIONS)
            if isinstance(legacy_roles, (list, tuple)) and any(role in ASSIGNMENT_OPTIONS for role in legacy_roles):
                permissions = _migrate_permissions(legacy_roles)
                roles_source = value.get("person_roles", [])
            else:
                permissions = _migrate_permissions(value.get("assignments", ALL_PERMISSIONS))
                roles_source = legacy_roles
        roles = [role for role in roles_source if role in PERSON_ROLE_OPTIONS] if isinstance(roles_source, (list, tuple)) else []
        auxiliary_until = _valid_until(value.get("auxiliary_pioneer_until"))
    else:
        permissions = list(ALL_PERMISSIONS)
        roles = []
        auxiliary_until = ""

    if "auxiliary_pioneer" in roles:
        if not auxiliary_until or date.fromisoformat(auxiliary_until) < current_date:
            roles = [role for role in roles if role != "auxiliary_pioneer"]
            auxiliary_until = ""
    else:
        auxiliary_until = ""

    return {
        "permissions": list(dict.fromkeys(permissions)),
        "roles": list(dict.fromkeys(roles)),
        "auxiliary_pioneer_until": auxiliary_until,
    }


def normalize_profiles(people: list[str], profiles: dict | None = None, today: date | None = None) -> dict[str, dict]:
    source = profiles if isinstance(profiles, dict) else {}
    return {person: normalize_profile(source.get(person), today=today) for person in people}


def eligible_people(people: list[str], profiles: dict, permission: str) -> list[str]:
    normalized = normalize_profiles(people, profiles)
    return [person for person in people if permission in normalized.get(person, {}).get("permissions", [])]
