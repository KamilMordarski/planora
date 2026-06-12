from copy import deepcopy


def weekly_row(start_date="", end_date="", group="", cleaning_person="", console_person="", microphone_1="", microphone_2=""):
    return {
        "start_date": start_date,
        "end_date": end_date,
        "group": group,
        "cleaning_person": cleaning_person,
        "console_person": console_person,
        "microphone_1": microphone_1,
        "microphone_2": microphone_2,
    }


def attendant_row(date="", lobby_attendant="", hall_attendant=""):
    return {
        "date": date,
        "lobby_attendant": lobby_attendant,
        "hall_attendant": hall_attendant,
    }


DEFAULT_PROJECT = {
    "template_id": "cleaning_attendants",
    "title": "PLAN SPRZĄTANIA SALI KRÓLESTWA\nI OBSŁUGI NAGŁOŚNIENIA",
    "attendant_title": "PLAN SŁUŻBY PORZĄDKOWEJ",
    "weekly_assignments": [],
    "attendant_assignments": [],
}


def create_default_project() -> dict:
    return deepcopy(DEFAULT_PROJECT)
