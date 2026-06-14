ROLE_OPTIONS = {
    "service_conductor": "Prowadzenie zbiórki do służby",
    "console": "Obsługa konsoli / Zoom",
    "microphone": "Obsługa mikrofonu",
    "attendant": "Służba porządkowa",
    "cleaning": "Sprzątanie sali",
    "chairman": "Przewodniczenie zebraniu",
    "public_speaker": "Wykład publiczny",
    "watchtower_conductor": "Prowadzenie Studium Strażnicy",
    "reader": "Czytanie / lektor",
    "midweek_participant": "Udział w zebraniu w tygodniu",
    "prayer": "Modlitwa na zebraniu",
}

ALL_ROLES = tuple(ROLE_OPTIONS)


def normalize_profiles(people: list[str], profiles: dict | None = None) -> dict[str, list[str]]:
    source = profiles if isinstance(profiles, dict) else {}
    normalized = {}
    for person in people:
        value = source.get(person, ALL_ROLES)
        if isinstance(value, dict):
            value = value.get("roles", ALL_ROLES)
        roles = [role for role in value if role in ROLE_OPTIONS] if isinstance(value, (list, tuple)) else list(ALL_ROLES)
        normalized[person] = roles
    return normalized


def eligible_people(people: list[str], profiles: dict, role: str) -> list[str]:
    normalized = normalize_profiles(people, profiles)
    return [person for person in people if role in normalized.get(person, [])]
