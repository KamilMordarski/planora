from copy import deepcopy


def meeting_row(date="", time="", place="", conductor="", date_color="") -> dict:
    return {
        "date": date,
        "time": time,
        "place": place,
        "conductor": conductor,
        "date_color": date_color,
    }


DEFAULT_PROJECT = {
    "template_id": "service_meetings",
    "title": "ZBIÓRKI DO SŁUŻBY",
    "period": "",
    "headers": {
        "date": "DATA",
        "time": "GODZINA",
        "place": "MIEJSCE",
        "conductor": "PROWADZĄCY",
    },
    "note": "",
    "colors": {
        "header_fill": "#425466",
        "header_text": "#ffffff",
        "accent_fill": "#dbe7ee",
        "note_fill": "#edf3f6",
        "text": "#1f2a33",
        "grid": "#73808c",
    },
    "meetings": [],
}


def create_default_project() -> dict:
    return deepcopy(DEFAULT_PROJECT)
