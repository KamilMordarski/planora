from app.config import APP_ICON
from app.templates.service_meetings.default_project import create_default_project


class ServiceMeetingsTemplate:
    id = "service_meetings"
    name = "Zbiórki do służby"
    description = "Edytowalny plan terminów, miejsc i prowadzących zbiórki do służby."
    icon = APP_ICON

    @property
    def editor_class(self):
        from app.templates.service_meetings.editor import ServiceMeetingsEditor

        return ServiceMeetingsEditor

    @property
    def renderer_class(self):
        from app.templates.service_meetings.renderer import ServiceMeetingsRenderer

        return ServiceMeetingsRenderer

    @property
    def default_project(self):
        return create_default_project()
