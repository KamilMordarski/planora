from copy import deepcopy


ROLE_MEMBER = "member"
ROLE_ASSISTANT = "assistant"
ROLE_LEADER = "leader"

ROLE_LABELS = {
    ROLE_MEMBER: "Członek grupy",
    ROLE_ASSISTANT: "Asystent grupowego",
    ROLE_LEADER: "Grupowy",
}


def member(name: str = "", role: str = ROLE_MEMBER) -> dict:
    return {"name": name, "role": role if role in ROLE_LABELS else ROLE_MEMBER}


def group(name: str, members: list[dict] | None = None) -> dict:
    return {"name": name, "members": list(members or [])}


DEFAULT_PROJECT = {
    "template_id": "field_service_groups",
    "congregation": "BOGUSZÓW - GORCE",
    "title": "GRUPY SŁUŻBY POLOWEJ",
    "groups": [group(f"GRUPA {index}") for index in range(1, 6)],
}


def create_default_project() -> dict:
    return deepcopy(DEFAULT_PROJECT)
