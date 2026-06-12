from app.config import APP_ICON
from app.templates.cleaning_attendants.default_project import create_default_project


class CleaningAttendantsTemplate:
    id = "cleaning_attendants"
    name = "Sprzątanie sali, nagłośnienie i porządkowi"
    description = "Tygodniowy plan sprzątania i nagłośnienia oraz dyżury porządkowych z kontrolą kolizji."
    icon = APP_ICON

    @property
    def editor_class(self):
        from app.templates.cleaning_attendants.editor import CleaningAttendantsEditor

        return CleaningAttendantsEditor

    @property
    def renderer_class(self):
        from app.templates.cleaning_attendants.renderer import CleaningAttendantsRenderer

        return CleaningAttendantsRenderer

    @property
    def default_project(self):
        return create_default_project()
