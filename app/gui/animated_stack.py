from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget


class AnimatedStackedWidget(QStackedWidget):
    def __init__(self, animations_enabled, parent=None):
        super().__init__(parent)
        self.animations_enabled = animations_enabled
        self._animation = None
        self._animated_widget = None

    def setCurrentWidgetAnimated(self, widget):
        if widget is self.currentWidget():
            return
        if self._animation is not None:
            self._animation.stop()
            self._finish_animation()
        self.setCurrentWidget(widget)
        if not self.animations_enabled():
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(220)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(self._finish_animation)
        self._animated_widget = widget
        self._animation = animation
        animation.start()

    def _finish_animation(self):
        animation = self._animation
        if self._animated_widget is not None:
            try:
                self._animated_widget.setGraphicsEffect(None)
            except RuntimeError:
                pass
        self._animated_widget = None
        self._animation = None
        if animation is not None:
            animation.deleteLater()
