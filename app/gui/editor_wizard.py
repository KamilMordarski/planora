from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.animated_stack import AnimatedStackedWidget
from app.gui.responsive import scrollable_widget


class EditorWizard(QWidget):
    step_changed = Signal(int)

    def __init__(self, animations_enabled: Callable[[], bool] | None = None, parent=None):
        super().__init__(parent)
        self._animations_enabled = animations_enabled or (lambda: True)
        self._steps = []
        self._step_buttons = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.header = QFrame()
        self.header.setObjectName("wizardHeader")
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(10, 6, 10, 6)
        self.header_layout.setSpacing(5)
        root.addWidget(self.header, 0)

        self.stack = AnimatedStackedWidget(self._animations_enabled)
        root.addWidget(self.stack, 1)

        self.footer = QFrame()
        self.footer.setObjectName("wizardFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(10, 6, 10, 6)
        self.step_hint = QLabel()
        self.step_hint.setObjectName("helpText")
        self.actions_menu = QMenu(self)
        self.actions_menu.aboutToShow.connect(self._rebuild_actions_menu)
        self.actions_button = QPushButton("Akcje kroku")
        self.actions_button.setMenu(self.actions_menu)
        self.back_button = QPushButton("← Poprzedni krok")
        self.next_button = QPushButton("Następny krok →")
        self.next_button.setObjectName("primaryButton")
        self.back_button.clicked.connect(self.previous_step)
        self.next_button.clicked.connect(self.next_step)
        footer_layout.addWidget(self.step_hint)
        footer_layout.addStretch()
        footer_layout.addWidget(self.actions_button)
        footer_layout.addWidget(self.back_button)
        footer_layout.addWidget(self.next_button)
        root.addWidget(self.footer, 0)

    def add_step(self, title: str, subtitle: str, widget: QWidget):
        index = len(self._steps)
        if widget.layout() is not None:
            widget.layout().setSizeConstraint(QLayout.SetMinimumSize)
        page = scrollable_widget(widget)
        self._steps.append((title, subtitle, widget, page))
        self.stack.addWidget(page)

        button = QPushButton(f"{index + 1}. {title}")
        button.setObjectName("wizardStep")
        button.setCheckable(True)
        button.setMinimumWidth(0)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        button.clicked.connect(lambda checked=False, value=index: self.set_step(value))
        self._step_buttons.append(button)
        self.header_layout.addWidget(button)
        if index == 0:
            self.set_step(0, animate=False)

    def add_header_action(self, button: QPushButton):
        self.header_layout.addStretch()
        self.header_layout.addWidget(button)

    def set_step(self, index: int, animate: bool = True):
        if not 0 <= index < len(self._steps):
            return
        title, subtitle, widget, page = self._steps[index]
        if animate:
            self.stack.setCurrentWidgetAnimated(page)
        else:
            self.stack.setCurrentWidget(page)
        for button_index, button in enumerate(self._step_buttons):
            button.setChecked(button_index == index)
            button.setProperty("complete", button_index < index)
            button.style().unpolish(button)
            button.style().polish(button)
        self.step_hint.setText(f"Krok {index + 1} z {len(self._steps)} · {subtitle}")
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < len(self._steps) - 1)
        self._current_content = widget
        self._rebuild_actions_menu()
        self.step_changed.emit(index)

    def current_step(self) -> int:
        return self.stack.currentIndex()

    def next_step(self):
        self.set_step(self.current_step() + 1)

    def previous_step(self):
        self.set_step(self.current_step() - 1)

    def _rebuild_actions_menu(self):
        self.actions_menu.clear()
        content = getattr(self, "_current_content", None)
        if content is None:
            self.actions_menu.addAction("Brak dodatkowych akcji").setEnabled(False)
            return
        buttons = [
            button
            for button in content.findChildren(QPushButton)
            if button.text().strip()
            and button.objectName() != "wizardStep"
            and button.isVisibleTo(content)
            and not button.property("excludeFromStepActions")
        ]
        if not buttons:
            self.actions_menu.addAction("Brak dodatkowych akcji").setEnabled(False)
            return
        for button in buttons:
            action = self.actions_menu.addAction(button.text().replace("&", ""))
            action.setEnabled(button.isEnabled())
            action.setToolTip(button.toolTip())
            action.triggered.connect(lambda _checked=False, target=button: target.click())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 760
        self.step_hint.setVisible(not compact)
        self.actions_button.setText("Akcje" if compact else "Akcje kroku")
        self.back_button.setText("Wstecz" if compact else "← Poprzedni krok")
        self.next_button.setText("Dalej" if compact else "Następny krok →")
        for index, (title, _subtitle, _widget, _page) in enumerate(self._steps):
            self._step_buttons[index].setText(str(index + 1) if compact else f"{index + 1}. {title}")


def page_layout(widget: QWidget, title: str, subtitle: str) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(14, 8, 14, 8)
    layout.setSpacing(8)
    heading = QLabel(title)
    heading.setObjectName("screenTitle")
    description = QLabel(subtitle)
    description.setObjectName("screenSubtitle")
    description.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(description)
    return layout
