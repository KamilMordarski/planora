import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QGridLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget


def configure_form(form: QFormLayout) -> QFormLayout:
    """Apply the same readable, responsive behavior to application forms."""
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.WrapLongRows)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    return form


def configure_editable_combo(field: QComboBox, minimum_contents_length: int = 8) -> QComboBox:
    """Keep editable selectors readable without letting long items stretch the whole editor."""
    field.setEditable(True)
    field.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    field.setMinimumContentsLength(minimum_contents_length)
    field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return field


class ResponsiveCardGrid(QWidget):
    def __init__(self, min_column_width: int = 320, max_columns: int = 3, parent=None):
        super().__init__(parent)
        self.min_column_width = min_column_width
        self.max_columns = max_columns
        self.cards: list[QWidget] = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignTop)

    def add_card(self, card: QWidget):
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.cards.append(card)
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        available = max(1, self.width())
        columns = max(1, min(self.max_columns, available // self.min_column_width))
        for index, card in enumerate(self.cards):
            self.grid.removeWidget(card)
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(self.max_columns):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)


class ResponsiveActionBar(QWidget):
    """A compact button row that wraps into a grid on narrow screens."""

    def __init__(self, buttons: list[QPushButton], min_button_width: int = 145, max_columns: int = 5, parent=None):
        super().__init__(parent)
        self.buttons = buttons
        self.min_button_width = min_button_width
        self.max_columns = max_columns
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        for button in buttons:
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        available = max(1, self.width() - self.grid.horizontalSpacing() * max(0, self.max_columns - 1))
        columns = max(1, min(self.max_columns, available // self.min_button_width))
        for index, button in enumerate(self.buttons):
            self.grid.removeWidget(button)
            self.grid.addWidget(button, index // columns, index % columns)
        for column in range(self.max_columns):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        rows = math.ceil(len(self.buttons) / columns) if self.buttons else 0
        button_height = max((button.sizeHint().height() for button in self.buttons), default=0)
        required_height = rows * button_height + max(0, rows - 1) * self.grid.verticalSpacing()
        if self.minimumHeight() != required_height:
            self.setMinimumHeight(required_height)
            self.updateGeometry()


def editor_toolbar(buttons: list[QPushButton]) -> QFrame:
    """Create a toolbar whose actions wrap instead of being clipped in a small window."""
    frame = QFrame()
    frame.setObjectName("editorToolbar")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.addWidget(ResponsiveActionBar(buttons, min_button_width=105, max_columns=len(buttons)))
    return frame
