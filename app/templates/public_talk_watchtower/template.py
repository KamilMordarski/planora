from app.config import APP_ICON
from app.templates.public_talk_watchtower.default_project import create_default_project


class PublicTalkWatchtowerTemplate:
    id = "public_talk_watchtower"
    name = "Wykład publiczny i Studium Strażnicy"
    description = "Grafik wykładu publicznego, studium Strażnicy oraz wydarzeń specjalnych."
    icon = APP_ICON

    @property
    def editor_class(self):
        from app.templates.public_talk_watchtower.editor import PublicTalkWatchtowerEditor

        return PublicTalkWatchtowerEditor

    @property
    def renderer_class(self):
        from app.templates.public_talk_watchtower.renderer import PublicTalkWatchtowerRenderer

        return PublicTalkWatchtowerRenderer

    @property
    def default_project(self):
        return create_default_project()
