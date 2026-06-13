from app.config import APP_ICON
from app.templates.field_service_groups.default_project import create_default_project


class FieldServiceGroupsTemplate:
    id = "field_service_groups"
    name = "Plan grup służby"
    description = "Edytowalny podział osób na grupy z wyróżnieniem grupowych, asystentów i członków."
    icon = APP_ICON

    @property
    def editor_class(self):
        from app.templates.field_service_groups.editor import FieldServiceGroupsEditor

        return FieldServiceGroupsEditor

    @property
    def renderer_class(self):
        from app.templates.field_service_groups.renderer import FieldServiceGroupsRenderer

        return FieldServiceGroupsRenderer

    @property
    def default_project(self):
        return create_default_project()
