from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPauseAnimation,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    Qt,
    QUrl,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from app.config import APP_ICON, STARTUP_SOUND
from app.core.app_info import APP_NAME, APP_TAGLINE


class StartupSplash(QWidget):
    finished = Signal()
    DURATION_MS = 3550

    def __init__(self, play_sound: bool = True, volume: int = 35, parent=None):
        super().__init__(parent)
        self.play_sound = play_sound
        self._base_panel_size = (360, 410)
        self._animation = None

        self.setObjectName("startupSplash")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(600, 540)

        self.panel = QFrame(self)
        self.panel.setObjectName("splashCard")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(38, 34, 38, 34)
        panel_layout.setSpacing(12)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)
        if APP_ICON.exists():
            self.logo.setPixmap(QPixmap(str(APP_ICON)).scaled(230, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        name = QLabel(APP_NAME)
        name.setObjectName("splashName")
        name.setAlignment(Qt.AlignCenter)
        subtitle = QLabel(APP_TAGLINE)
        subtitle.setObjectName("splashSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        panel_layout.addWidget(self.logo, 1)
        panel_layout.addWidget(name)
        panel_layout.addWidget(subtitle)

        self.opacity = QGraphicsOpacityEffect(self.panel)
        self.opacity.setOpacity(0.0)
        self.panel.setGraphicsEffect(self.opacity)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(max(0, min(100, int(volume))) / 100)
        self.player.setAudioOutput(self.audio)
        if STARTUP_SOUND.exists():
            self.player.setSource(QUrl.fromLocalFile(str(STARTUP_SOUND)))

        self._set_scale(0.55)

    def start(self):
        self._center_on_screen()
        self.show()
        self.raise_()
        if self.play_sound and STARTUP_SOUND.exists():
            self.player.play()

        fade_in = QPropertyAnimation(self.opacity, b"opacity", self)
        fade_in.setDuration(260)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)

        pop = QVariantAnimation(self)
        pop.setDuration(520)
        pop.setStartValue(0.55)
        pop.setEndValue(1.08)
        pop.setEasingCurve(QEasingCurve.OutBack)
        pop.valueChanged.connect(self._set_scale)

        settle = QVariantAnimation(self)
        settle.setDuration(180)
        settle.setStartValue(1.08)
        settle.setEndValue(1.0)
        settle.setEasingCurve(QEasingCurve.OutCubic)
        settle.valueChanged.connect(self._set_scale)

        pop_sequence = QParallelAnimationGroup(self)
        pop_sequence.addAnimation(fade_in)
        pop_sequence.addAnimation(pop)

        fade_out = QPropertyAnimation(self.opacity, b"opacity", self)
        fade_out.setDuration(650)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(pop_sequence)
        sequence.addAnimation(settle)
        sequence.addAnimation(QPauseAnimation(self.DURATION_MS - 520 - 180 - 650, self))
        sequence.addAnimation(fade_out)
        sequence.finished.connect(self._finish)
        self._animation = sequence
        sequence.start()

    def _set_scale(self, value):
        scale = float(value)
        width = round(self._base_panel_size[0] * scale)
        height = round(self._base_panel_size[1] * scale)
        self.panel.setGeometry(QRect((self.width() - width) // 2, (self.height() - height) // 2, width, height))

    def _center_on_screen(self):
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _finish(self):
        self.player.stop()
        self.hide()
        self.finished.emit()
        self.deleteLater()
