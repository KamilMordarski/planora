from app.config import APP_ICON
from app.templates.midweek_meeting.default_project import create_default_project


class MidweekMeetingTemplate:
    id = "midweek_meeting"
    name = "Plan zebrań w tygodniu"
    description = "Program zebrań w tygodniu z kolorowymi sekcjami oraz wydarzeniami specjalnymi."
    icon = APP_ICON

    @property
    def editor_class(self):
        from app.templates.midweek_meeting.editor import MidweekMeetingEditor

        return MidweekMeetingEditor

    @property
    def renderer_class(self):
        from app.templates.midweek_meeting.renderer import MidweekMeetingRenderer

        return MidweekMeetingRenderer

    @property
    def default_project(self):
        return create_default_project()
