from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.gui.responsive import ResponsiveCardGrid
from app.gui.template_icons import template_icon


class ScheduleTypeScreen(QWidget):
    def __init__(self, templates: list, choose_template: Callable, go_back: Callable):
        super().__init__()
        self.root = QVBoxLayout(self)
        root = self.root
        root.setContentsMargins(42, 30, 42, 30)

        top = QHBoxLayout()
        back = QPushButton("← Menu główne")
        back.clicked.connect(go_back)
        top.addWidget(back)
        top.addStretch()
        root.addLayout(top)

        title = QLabel("Wybierz typ grafiku")
        title.setObjectName("screenTitle")
        root.addWidget(title)
        subtitle = QLabel("Każdy generator ma własny formularz, podgląd i sposób eksportu.")
        subtitle.setObjectName("screenSubtitle")
        root.addWidget(subtitle)
        root.addSpacing(14)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        cards = ResponsiveCardGrid(min_column_width=310, max_columns=3)
        content_layout.addWidget(cards)
        content_layout.addStretch()

        for index, template in enumerate(templates):
            card = QFrame()
            card.setObjectName("templateCard")
            card.setMinimumHeight(250)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(24, 22, 24, 22)

            icon = QLabel()
            icon.setAlignment(Qt.AlignCenter)
            icon.setPixmap(template_icon(template.id, 92))
            card_layout.addWidget(icon)

            name = QLabel(template.name)
            name.setObjectName("cardTitle")
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(name)

            description = QLabel(template.description)
            description.setObjectName("screenSubtitle")
            description.setWordWrap(True)
            description.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(description)
            card_layout.addStretch()

            choose = QPushButton("Utwórz grafik")
            choose.setObjectName("primaryButton")
            choose.setMinimumHeight(34)
            choose.clicked.connect(lambda checked=False, template_id=template.id: choose_template(template_id))
            card_layout.addWidget(choose)
            cards.add_card(card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        root.addWidget(scroll)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() < 700:
            self.root.setContentsMargins(12, 10, 12, 10)
        elif self.width() < 1000:
            self.root.setContentsMargins(24, 18, 24, 18)
        else:
            self.root.setContentsMargins(42, 30, 42, 30)
