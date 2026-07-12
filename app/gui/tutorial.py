from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


TUTORIAL_PROPERTY = "planoraTutorialId"


def tutorial_anchor(widget: QWidget, anchor_id: str) -> QWidget:
    widget.setProperty(TUTORIAL_PROPERTY, anchor_id)
    return widget


def find_tutorial_anchor(root: QWidget, anchor_id: str) -> QWidget | None:
    if root.property(TUTORIAL_PROPERTY) == anchor_id:
        return root
    return next(
        (
            widget
            for widget in root.findChildren(QWidget)
            if widget.property(TUTORIAL_PROPERTY) == anchor_id
        ),
        None,
    )


@dataclass(frozen=True)
class TutorialStep:
    title: str
    text: str
    target: QWidget | Callable[[], QWidget | None] | None = None
    before: Callable[[], None] | None = None


class TutorialOverlay(QWidget):
    closed = Signal(bool)

    def __init__(self, host: QWidget, title: str, steps: list[TutorialStep]):
        super().__init__(host)
        self.host = host
        self.tutorial_title = title
        self.steps = list(steps)
        self.index = 0
        self.target: QWidget | None = None
        self.highlight_rect = QRect()
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.StrongFocus)

        self.card = QFrame(self)
        self.card.setObjectName("tutorialCard")
        self.card.setStyleSheet(
            """
            QFrame#tutorialCard {
                background: #172435;
                border: 1px solid #4e6680;
                border-radius: 14px;
            }
            QFrame#tutorialCard QLabel {
                color: #f7fafc;
                background: transparent;
            }
            QFrame#tutorialCard QLabel#tutorialCounter {
                color: #a9bdd1;
                font-size: 11px;
            }
            QFrame#tutorialCard QLabel#tutorialTitle {
                font-size: 17px;
                font-weight: 700;
            }
            QFrame#tutorialCard QPushButton {
                color: #f7fafc;
                background: #26394d;
                border: 1px solid #4e6680;
                border-radius: 8px;
                padding: 7px 12px;
            }
            QFrame#tutorialCard QPushButton#tutorialNext {
                color: #102033;
                background: #9fd4ff;
                border-color: #9fd4ff;
                font-weight: 700;
            }
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 16, 18, 14)
        card_layout.setSpacing(8)
        self.counter = QLabel()
        self.counter.setObjectName("tutorialCounter")
        self.heading = QLabel()
        self.heading.setObjectName("tutorialTitle")
        self.heading.setWordWrap(True)
        self.description = QLabel()
        self.description.setWordWrap(True)
        card_layout.addWidget(self.counter)
        card_layout.addWidget(self.heading)
        card_layout.addWidget(self.description)

        actions = QHBoxLayout()
        self.skip_button = QPushButton("Pomiń samouczek")
        self.back_button = QPushButton("Wstecz")
        self.next_button = QPushButton("Dalej")
        self.next_button.setObjectName("tutorialNext")
        actions.addWidget(self.skip_button)
        actions.addStretch()
        actions.addWidget(self.back_button)
        actions.addWidget(self.next_button)
        card_layout.addLayout(actions)

        self.skip_button.clicked.connect(lambda: self.finish(False))
        self.back_button.clicked.connect(self.previous)
        self.next_button.clicked.connect(self.next)
        self.host.installEventFilter(self)

    def start(self):
        if not self.steps:
            self.deleteLater()
            return
        self.setGeometry(self.host.rect())
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self.show_step(0)

    def show_step(self, index: int):
        if not 0 <= index < len(self.steps):
            return
        self.index = index
        step = self.steps[index]
        if step.before:
            step.before()
        self.counter.setText(
            f"{self.tutorial_title}  ·  krok {index + 1} z {len(self.steps)}"
        )
        self.heading.setText(step.title)
        self.description.setText(step.text)
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("Zakończ" if index == len(self.steps) - 1 else "Dalej")
        QTimer.singleShot(80, self._position_step)

    def next(self):
        if self.index >= len(self.steps) - 1:
            self.finish(True)
            return
        self.show_step(self.index + 1)

    def previous(self):
        if self.index > 0:
            self.show_step(self.index - 1)

    def finish(self, completed: bool):
        self.host.removeEventFilter(self)
        self.hide()
        self.closed.emit(completed)
        self.deleteLater()

    def _position_step(self):
        step = self.steps[self.index]
        target = step.target() if callable(step.target) else step.target
        self.target = target if target and target.isVisible() else None
        if self.target is not None:
            self._ensure_visible(self.target)
            top_left = self.target.mapTo(self, QPoint(0, 0))
            rect = QRect(top_left, self.target.size()).adjusted(-7, -7, 7, 7)
            self.highlight_rect = rect.intersected(self.rect().adjusted(8, 8, -8, -8))
        else:
            self.highlight_rect = QRect()
        self.card.setFixedWidth(max(300, min(430, self.width() - 28)))
        self.card.adjustSize()
        self._position_card()
        self.update()
        self.raise_()

    @staticmethod
    def _ensure_visible(target: QWidget):
        current = target.parentWidget()
        while current is not None:
            if isinstance(current, QScrollArea):
                current.ensureWidgetVisible(target, 30, 30)
            current = current.parentWidget()

    def _position_card(self):
        margin = 14
        card_size = self.card.sizeHint()
        width = min(self.card.width(), self.width() - margin * 2)
        height = min(card_size.height(), self.height() - margin * 2)
        if self.highlight_rect.isValid():
            below = self.highlight_rect.bottom() + 14
            above = self.highlight_rect.top() - height - 14
            y = below if below + height <= self.height() - margin else max(margin, above)
            x = max(
                margin,
                min(
                    self.highlight_rect.center().x() - width // 2,
                    self.width() - width - margin,
                ),
            )
        else:
            x = max(margin, (self.width() - width) // 2)
            y = max(margin, (self.height() - height) // 2)
        self.card.setGeometry(x, y, width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shade = QPainterPath()
        shade.setFillRule(Qt.OddEvenFill)
        shade.addRect(QRectF(self.rect()))
        if self.highlight_rect.isValid():
            shade.addRoundedRect(QRectF(self.highlight_rect), 10, 10)
        painter.fillPath(shade, QColor(8, 15, 25, 185))
        if self.highlight_rect.isValid():
            painter.setPen(QPen(QColor("#9fd4ff"), 3))
            painter.drawRoundedRect(self.highlight_rect, 10, 10)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._position_step)

    def eventFilter(self, watched, event):
        if watched is self.host and event.type() == QEvent.Resize:
            self.setGeometry(self.host.rect())
            QTimer.singleShot(0, self._position_step)
        return False

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.finish(False)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Right):
            self.next()
            return
        if event.key() == Qt.Key_Left:
            self.previous()
            return
        super().keyPressEvent(event)


def _step(
    editor: QWidget,
    step_index: int,
    anchor_id: str,
    title: str,
    text: str,
) -> TutorialStep:
    wizard = editor.wizard
    return TutorialStep(
        title,
        text,
        target=lambda: find_tutorial_anchor(editor, anchor_id),
        before=lambda: wizard.set_step(step_index, animate=False),
    )


def editor_tutorial_steps(template_id: str, editor: QWidget) -> list[TutorialStep]:
    common_preview = (
        "Sprawdź gotowy dokument. Tutaj możesz go powiększyć, wydrukować albo wyeksportować "
        "do PDF i JPG. Motyw aplikacji nie zmienia wyglądu eksportu."
    )
    definitions = {
        "public_talk_watchtower": [
            (0, "document", "Nadaj dokumentowi nazwę", "Wpisz tytuł, który pojawi się na gotowym planie."),
            (0, "new_entry", "Przygotuj nowy tydzień", "Kliknij „Nowy formularz”, aby rozpocząć pusty wpis bez nadpisywania wcześniejszego tygodnia."),
            (1, "date", "Wpisz datę", "Data nie jest narzucona. Wpisz dzień odpowiadający rzeczywistemu terminowi zebrania."),
            (1, "details", "Przypisz program i osoby", "Uzupełnij temat wykładu, Studium Strażnicy oraz wybierz osoby z biblioteki."),
            (1, "add_entry", "Dodaj wypełniony tydzień", "Ten przycisk zapisuje cały widoczny formularz jako nową pozycję planu."),
            (2, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "cleaning_attendants": [
            (0, "document", "Ustaw tytuły dokumentu", "Nadaj nazwy części dotyczącej sprzątania oraz służby porządkowej."),
            (1, "weekly_form", "Uzupełnij tydzień", "Wybierz zakres dat i grupę. Grupowy może zostać automatycznie podpowiedziany jako osoba odpowiedzialna za sprzątanie."),
            (1, "add_weekly", "Dodaj tydzień", "Dodaj aktualnie wypełniony zakres wraz z konsolą i mikrofonami."),
            (2, "attendant_form", "Dodaj porządkowych", "Ustaw rzeczywistą datę zebrania i przypisz osoby na hol oraz salę."),
            (2, "add_attendant", "Zapisz dyżur", "Dodaj dyżur do listy. Kontrola kolizji odświeży się automatycznie."),
            (3, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "midweek_meeting": [
            (0, "document", "Ustaw dokument i dzień", "Wpisz nazwę zboru oraz wybierz domyślny dzień zebrania. Nie musi to być środa."),
            (0, "new_entry", "Rozpocznij nowe zebranie", "Przygotuj pusty formularz albo przejdź do importu programu z JW w kroku „Program”."),
            (1, "date", "Wybierz rzeczywistą datę", "Ustaw dzień konkretnego zebrania oraz uzupełnij rozpoczęcie, zakończenie i osoby."),
            (1, "add_entry", "Dodaj zebranie", "Formularz zostanie dodany jako nowy termin, bez wcześniejszego tworzenia pustej pozycji."),
            (2, "program_actions", "Utwórz program", "Dodaj szablon punktów, puste sekcje albo pobierz wybrany tydzień z JW. Import użyje ustawionego dnia zebrania."),
            (2, "item_details", "Uzupełnij punkt", "Wybierz sekcję i punkt, a następnie wpisz godzinę, nazwę i uczestników. Numer pojawi się automatycznie."),
            (3, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "field_service_groups": [
            (0, "document", "Ustaw nagłówek", "Wpisz zbór lub miejscowość oraz nazwę dokumentu."),
            (0, "add_group", "Dodaj potrzebne grupy", "Możesz utworzyć dowolną liczbę grup i zmieniać ich kolejność."),
            (1, "group_members", "Dodaj osoby do grupy", "Wybierz grupę, dodaj osoby z biblioteki i przypisz rolę grupowego, asystenta lub członka."),
            (2, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "service_meetings": [
            (0, "document", "Ustaw wygląd dokumentu", "Wpisz tytuł, okres, nazwy kolumn i opcjonalną notatkę."),
            (1, "meeting_form", "Uzupełnij zbiórkę", "Wpisz opis dnia, godzinę, miejsce oraz wybierz osobę prowadzącą."),
            (1, "add_entry", "Dodaj termin", "Dodaj cały wypełniony formularz do planu jednym kliknięciem."),
            (2, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
    }
    return [
        _step(editor, index, anchor, title, text)
        for index, anchor, title, text in definitions.get(template_id, [])
    ]
