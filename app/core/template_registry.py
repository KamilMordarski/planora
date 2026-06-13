from app.templates.public_talk_watchtower.template import PublicTalkWatchtowerTemplate
from app.templates.cleaning_attendants.template import CleaningAttendantsTemplate
from app.templates.midweek_meeting.template import MidweekMeetingTemplate
from app.templates.field_service_groups.template import FieldServiceGroupsTemplate
from app.templates.service_meetings.template import ServiceMeetingsTemplate


TEMPLATES = [
    PublicTalkWatchtowerTemplate(),
    CleaningAttendantsTemplate(),
    MidweekMeetingTemplate(),
    FieldServiceGroupsTemplate(),
    ServiceMeetingsTemplate(),
]


class TemplateRegistry:
    @staticmethod
    def all():
        return list(TEMPLATES)

    @staticmethod
    def get(template_id: str):
        for template in TEMPLATES:
            if template.id == template_id:
                return template
        return None

    @staticmethod
    def for_project(project: dict):
        return TemplateRegistry.get(project.get("template_id", "public_talk_watchtower"))
