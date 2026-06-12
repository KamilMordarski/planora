import copy


DEFAULT_PROJECT = {
    "template_id": "public_talk_watchtower",
    "title": "WYKŁAD PUBLICZNY I STUDIUM STRAŻNICY",
    "weeks": [],
}


def create_default_project() -> dict:
    return copy.deepcopy(DEFAULT_PROJECT)
