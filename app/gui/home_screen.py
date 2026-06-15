from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QBoxLayout, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.config import APP_ICON
from app.core.app_info import (
    APP_AUTHOR,
    APP_AUTHOR_URL,
    APP_DISCLAIMER,
    APP_DOCS_URL,
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    LAST_UPDATE,
)
from app.gui.responsive import ResponsiveCardGrid


class HomeScreen(QWidget):
    def __init__(
        self,
        create_schedule: Callable,
        open_project: Callable,
        edit_people: Callable,
        check_updates: Callable,
        open_settings: Callable,
        open_guide: Callable,
        open_planning_tools: Callable,
        open_project_center: Callable,
        open_project_transfer: Callable,
    ):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(48, 34, 48, 34)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        top = QHBoxLayout()
        brand = QLabel(f"{APP_NAME}  •  {APP_VERSION}")
        brand.setObjectName("sectionTitle")
        top.addWidget(brand)
        top.addStretch()
        guide = QPushButton("Poradnik")
        settings = QPushButton("Ustawienia")
        guide.clicked.connect(open_guide)
        settings.clicked.connect(open_settings)
        top.addWidget(guide)
        top.addWidget(settings)
        root.addLayout(top)

        hero = QFrame()
        hero.setObjectName("heroCard")
        self.hero_layout = QBoxLayout(QBoxLayout.LeftToRight, hero)
        hero_layout = self.hero_layout
        hero_layout.setContentsMargins(34, 28, 34, 28)
        icon = QLabel()
        if APP_ICON.exists():
            icon.setPixmap(QPixmap(str(APP_ICON)).scaled(126, 126, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hero_layout.addWidget(icon)
        hero_text = QVBoxLayout()
        name = QLabel(APP_TAGLINE)
        name.setObjectName("appName")
        name.setWordWrap(True)
        subtitle = QLabel("Wybierz generator, przypisz osoby, sprawdź podgląd i wyeksportuj gotowy dokument.")
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        self.actions = QBoxLayout(QBoxLayout.LeftToRight)
        actions = self.actions
        create = QPushButton("Utwórz nowy grafik")
        create.setObjectName("primaryButton")
        create.setMinimumHeight(36)
        open_button = QPushButton("Otwórz projekt")
        open_button.setMinimumHeight(36)
        create.clicked.connect(create_schedule)
        open_button.clicked.connect(open_project)
        actions.addWidget(create)
        actions.addWidget(open_button)
        actions.addStretch()
        hero_text.addWidget(name)
        hero_text.addWidget(subtitle)
        hero_text.addSpacing(10)
        hero_text.addLayout(actions)
        hero_layout.addLayout(hero_text, 1)
        root.addWidget(hero)
        root.addSpacing(18)

        disclaimer = QFrame()
        disclaimer.setObjectName("disclaimerCard")
        disclaimer_layout = QVBoxLayout(disclaimer)
        disclaimer_title = QLabel("Niezależne narzędzie")
        disclaimer_title.setObjectName("sectionTitle")
        disclaimer_text = QLabel(APP_DISCLAIMER)
        disclaimer_text.setWordWrap(True)
        disclaimer_text.setObjectName("screenSubtitle")
        disclaimer_layout.addWidget(disclaimer_title)
        disclaimer_layout.addWidget(disclaimer_text)
        root.addWidget(disclaimer)
        root.addSpacing(12)

        duty_panel = QFrame()
        duty_panel.setObjectName("infoCard")
        duty_layout = QHBoxLayout(duty_panel)
        duty_text = QVBoxLayout()
        duty_title = QLabel("Nadchodzące obowiązki")
        duty_title.setObjectName("sectionTitle")
        self.duty_summary = QLabel("Ładowanie lokalnego kalendarza…")
        self.duty_summary.setObjectName("screenSubtitle")
        self.duty_summary.setWordWrap(True)
        open_duties = QPushButton("Otwórz panel")
        open_duties.setObjectName("primaryButton")
        open_duties.clicked.connect(open_project_center)
        duty_text.addWidget(duty_title)
        duty_text.addWidget(self.duty_summary)
        duty_layout.addLayout(duty_text, 1)
        duty_layout.addWidget(open_duties)
        root.addWidget(duty_panel)
        root.addSpacing(12)

        section = QLabel("Narzędzia")
        section.setObjectName("screenTitle")
        root.addWidget(section)
        cards = ResponsiveCardGrid(min_column_width=280, max_columns=3)
        items = [
            ("Biblioteka osób i role", "Wspólna lista uczestników, ról i możliwych przydziałów.", edit_people),
            (
                "Import i eksport grafików",
                "Przenoś edytowalne projekty JSON między komputerami i folderami.",
                open_project_transfer,
            ),
            ("Asystent planowania", "Automatyczne daty, przydziały, masowa edycja i kalendarz.", open_planning_tools),
            (
                "Centrum projektów",
                "Obowiązki, globalne kolizje, wiadomości, statystyki i drukowanie zbiorcze.",
                open_project_center,
            ),
            ("Sprawdź aktualizacje", "Sprawdź, czy dostępna jest nowsza wersja aplikacji.", check_updates),
            ("Poradnik", "Poznaj cały proces tworzenia i eksportowania grafików.", open_guide),
            (
                "Dokumentacja online",
                "Pełny opis funkcji, generatorów i aktualnych sposobów pracy z Planorą.",
                lambda: QDesktopServices.openUrl(QUrl(APP_DOCS_URL)),
            ),
        ]
        for index, (title, description, callback) in enumerate(items):
            card = QFrame()
            card.setObjectName("infoCard")
            card_layout = QVBoxLayout(card)
            card_title = QLabel(title)
            card_title.setObjectName("cardTitle")
            card_text = QLabel(description)
            card_text.setObjectName("screenSubtitle")
            card_text.setWordWrap(True)
            button = QPushButton("Otwórz")
            button.clicked.connect(callback)
            card_layout.addWidget(card_title)
            card_layout.addWidget(card_text)
            card_layout.addStretch()
            card_layout.addWidget(button)
            cards.add_card(card)
        root.addWidget(cards)
        root.addStretch()

        footer = QLabel(
            f'Autor: <a href="{APP_AUTHOR_URL}">{APP_AUTHOR}</a>'
            f'  •  <a href="{APP_DOCS_URL}">Dokumentacja</a>'
            f"  •  Ostatnia aktualizacja: {LAST_UPDATE}"
        )
        footer.setObjectName("appInfo")
        footer.setAlignment(Qt.AlignCenter)
        footer.setOpenExternalLinks(True)
        footer.setTextInteractionFlags(Qt.TextBrowserInteraction)
        root.addWidget(footer)

    def set_duty_summary(self, text: str):
        self.duty_summary.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 820
        self.hero_layout.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self.actions.setDirection(QBoxLayout.TopToBottom if self.width() < 600 else QBoxLayout.LeftToRight)
        content = self.findChild(QScrollArea).widget()
        margins = 16 if self.width() < 760 else 48
        content.layout().setContentsMargins(margins, 24, margins, 24)
