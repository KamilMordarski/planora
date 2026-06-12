from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QGridLayout, QSizePolicy, QWidget


def configure_form(form: QFormLayout) -> QFormLayout:
    """Apply the same readable, responsive behavior to application forms."""
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.WrapLongRows)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    return form


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
