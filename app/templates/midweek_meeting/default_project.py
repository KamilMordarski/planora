from copy import deepcopy


def program_item(time="", title="", participant_1="", participant_2="", role_1="", role_2=""):
    return {
        "time": time,
        "title": title,
        "participant_1": participant_1,
        "participant_2": participant_2,
        "role_1": role_1,
        "role_2": role_2,
    }


def section(title, color, items=None):
    return {"title": title, "color": color, "items": items or []}


def normal_meeting(date=""):
    return {
        "type": "normal",
        "date": date,
        "bible_reading": "",
        "chairman": "",
        "opening_prayer": "",
        "opening_song": "",
        "opening_song_time": "",
        "opening_comments": "",
        "opening_comments_time": "",
        "sections": [],
        "closing_comments": "",
        "closing_comments_time": "",
        "closing_song": "",
        "closing_song_time": "",
        "closing_prayer": "",
    }


def special_event(date=""):
    return {
        "type": "special",
        "date": date,
        "special_title": "",
        "special_subtitle": "",
        "image_path": "",
    }


DEFAULT_PROJECT = {
    "template_id": "midweek_meeting",
    "document_title": "Plan zebrań w tygodniu",
    "congregation": "",
    "meeting_weekday": 3,
    "meetings": [],
}


def create_default_project() -> dict:
    return deepcopy(DEFAULT_PROJECT)
