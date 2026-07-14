from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


TUTORIAL_PROPERTY = "planoraTutorialId"
BLOCK_OBJECT_NAMES = {
    "heroCard",
    "infoCard",
    "disclaimerCard",
    "templateCard",
    "editorToolbar",
    "editorContextBar",
    "wizardHeader",
    "wizardFooter",
}
BLOCK_CLASS_NAMES = {"ResponsiveActionBar", "ResponsiveCardGrid"}


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
            f"{self.tutorial_title}  -  krok {index + 1} z {len(self.steps)}"
        )
        self.heading.setText(step.title)
        self.description.setText(step.text)
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("Zakończ" if index == len(self.steps) - 1 else "Dalej")
        QTimer.singleShot(90, self._position_step)

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
        self.target = self._preferred_block(target)
        if self.target is not None:
            self._ensure_visible(self.target)
            self.highlight_rect = self._visible_rect_for(self.target)
        else:
            self.highlight_rect = QRect()
        self._resize_card()
        self._position_card()
        self.update()
        self.raise_()

    def _preferred_block(self, target: QWidget | None) -> QWidget | None:
        if target is None or not target.isVisible():
            return None
        if target.width() >= 180 and target.height() >= 70:
            return target

        current = target.parentWidget()
        while current is not None and current is not self.host:
            if not current.isVisible():
                current = current.parentWidget()
                continue
            if self._is_tutorial_block(current):
                return current
            current = current.parentWidget()
        return target

    @staticmethod
    def _is_tutorial_block(widget: QWidget) -> bool:
        return (
            isinstance(widget, QGroupBox)
            or widget.objectName() in BLOCK_OBJECT_NAMES
            or widget.__class__.__name__ in BLOCK_CLASS_NAMES
        )

    @staticmethod
    def _ensure_visible(target: QWidget):
        current = target.parentWidget()
        while current is not None:
            if isinstance(current, QScrollArea):
                current.ensureWidgetVisible(target, 36, 36)
            current = current.parentWidget()

    def _visible_rect_for(self, target: QWidget) -> QRect:
        rect = QRect(target.mapTo(self, QPoint(0, 0)), target.size())
        current: QWidget | None = target.parentWidget()
        while current is not None:
            if current.isVisible():
                clip = QRect(current.mapTo(self, QPoint(0, 0)), current.size())
                rect = rect.intersected(clip)
            if isinstance(current.parentWidget(), QScrollArea):
                viewport = current.parentWidget().viewport()
                clip = QRect(viewport.mapTo(self, QPoint(0, 0)), viewport.size())
                rect = rect.intersected(clip)
            if current is self.host:
                break
            current = current.parentWidget()
        rect = rect.adjusted(-7, -7, 7, 7).intersected(self.rect().adjusted(8, 8, -8, -8))
        if rect.width() < 18 or rect.height() < 18:
            return QRect()
        return rect

    def _resize_card(self):
        available_width = max(1, self.width() - 28)
        preferred = 430 if self.width() >= 520 else 360
        width = max(260, min(preferred, available_width))
        self.card.setFixedWidth(width)
        self.card.setMinimumHeight(0)
        self.card.setMaximumHeight(16_777_215)
        self.card.adjustSize()
        max_height = max(180, self.height() - 28)
        if self.card.height() > max_height:
            self.card.setFixedHeight(max_height)
        else:
            self.card.setFixedHeight(self.card.sizeHint().height())

    def _position_card(self):
        margin = 14
        width = min(self.card.width(), self.width() - margin * 2)
        height = min(self.card.height(), self.height() - margin * 2)
        if self.highlight_rect.isValid():
            below_space = self.height() - self.highlight_rect.bottom() - margin
            above_space = self.highlight_rect.top() - margin
            if below_space >= height + 14 or below_space >= above_space:
                y = min(self.highlight_rect.bottom() + 14, self.height() - height - margin)
            else:
                y = max(margin, self.highlight_rect.top() - height - 14)
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
            shade.addRoundedRect(QRectF(self.highlight_rect), 12, 12)
        painter.fillPath(shade, QColor(8, 15, 25, 185))
        if self.highlight_rect.isValid():
            painter.setPen(QPen(QColor("#9fd4ff"), 3))
            painter.drawRoundedRect(self.highlight_rect, 12, 12)

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
        "Na końcu sprawdź podgląd strony. Jeśli coś nie pasuje, wróć do poprzedniego kroku, "
        "popraw dane i dopiero wtedy użyj drukowania albo eksportu PDF/JPG."
    )
    definitions = {
        "public_talk_watchtower": [
            (0, "document", "Nazwij dokument", "W tym bloku ustawiasz tytuł widoczny na gotowym planie."),
            (0, "new_entry", "Zarządzaj tygodniami", "Tu widzisz listę tygodni. Możesz wybrać istniejący wpis, dodać nowy, usunąć go albo zmienić kolejność."),
            (1, "date", "Uzupełnij dane tygodnia", "Wpisz datę i rodzaj tygodnia. Ten krok nie wymaga wcześniejszego dodawania pustej pozycji."),
            (1, "details", "Przypisz program i osoby", "W tym bloku uzupełniasz temat wykładu, prowadzących oraz lektora z biblioteki osób."),
            (1, "add_entry", "Dodaj gotowy wpis", "Po uzupełnieniu formularza kliknij dodawanie z formularza, a tydzień trafi na listę."),
            (2, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "cleaning_attendants": [
            (0, "document", "Ustaw tytuły dokumentu", "Nadaj nazwy części dotyczącej sprzątania oraz służby porządkowej."),
            (1, "weekly_form", "Uzupełnij tydzień", "Wybierz zakres dat, grupę, osobę od sprzątania, konsolę oraz mikrofony."),
            (1, "add_weekly", "Dodaj tydzień", "Dodaj aktualnie wypełniony zakres do listy. Grupowy może być podpowiedziany automatycznie."),
            (2, "attendant_form", "Dodaj porządkowych", "Ustaw rzeczywistą datę zebrania i przypisz osoby na hol oraz salę."),
            (2, "add_attendant", "Zapisz dyżur", "Po dodaniu dyżuru kontrola kolizji odświeży się automatycznie."),
            (3, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "midweek_meeting": [
            (0, "document", "Ustaw dokument i dzień", "Wpisz nazwę zboru oraz domyślny dzień zebrania. Zebranie nie musi być w środę."),
            (0, "new_entry", "Lista zebrań", "Tutaj dodajesz, duplikujesz i układasz kolejność zebrań w projekcie."),
            (1, "date", "Dane konkretnego zebrania", "Ustaw datę, przewodniczącego, modlitwy oraz początek i zakończenie programu."),
            (1, "add_entry", "Dodaj wypełnione zebranie", "Ten przycisk tworzy nowy termin z widocznego formularza, bez pustego wpisu po drodze."),
            (2, "program_actions", "Sekcje i import z JW", "W tym bloku dodasz sekcje, szablon punktów albo wkleisz link z JW do wybranego tygodnia."),
            (2, "item_details", "Edycja punktu", "Wybierz punkt z listy i uzupełnij godzinę, nazwę oraz osoby. Numer punktu pojawi się automatycznie."),
            (3, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "field_service_groups": [
            (0, "document", "Ustaw nagłówek", "Wpisz zbór lub miejscowość oraz nazwę dokumentu. Domyślnie dokument jest pusty."),
            (0, "add_group", "Dodaj potrzebne grupy", "Tu kontrolujesz liczbę grup i ich kolejność w gotowym eksporcie."),
            (1, "group_members", "Dodaj osoby do grupy", "Wybierz grupę, dodaj osoby z biblioteki i przypisz rolę: grupowy, asystent albo członek."),
            (2, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
        "service_meetings": [
            (0, "document", "Ustaw teksty dokumentu", "Wpisz tytuł, okres, nazwy kolumn i notatkę pod tabelą."),
            (1, "meeting_form", "Uzupełnij zbiórkę", "W tym bloku wpisujesz opis dnia, godzinę, miejsce i prowadzącego."),
            (1, "add_entry", "Dodaj termin", "Dodaj cały wypełniony formularz do planu jednym kliknięciem."),
            (2, "preview", "Sprawdź i wyeksportuj", common_preview),
        ],
    }
    return [
        _step(editor, index, anchor, title, text)
        for index, anchor, title, text in definitions.get(template_id, [])
    ]
