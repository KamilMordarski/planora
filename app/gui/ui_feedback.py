import math
import struct
import time
import wave
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QComboBox, QGraphicsOpacityEffect, QPushButton

from app.config import USER_DATA_DIR
from app.gui.animated_stack import animation_duration


class UiFeedback(QObject):
    SOUND_VERSION = 3

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.effects: dict[str, QSoundEffect] = {}
        self.animations = {}
        self._last_hover_sound = 0.0
        sound_names = ("click", "hover", "navigate", "switch", "add", "remove", "open", "save", "export", "confirm")
        self._cleanup_old_sounds(sound_names)
        for name in sound_names:
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(str(self._ensure_sound(name))))
            self.effects[name] = effect
        self._update_volume()

    @classmethod
    def _cleanup_old_sounds(cls, sound_names):
        current = {f"ui-{name}-v{cls.SOUND_VERSION}.wav" for name in sound_names}
        for path in USER_DATA_DIR.glob("ui-*.wav"):
            if path.name not in current:
                path.unlink(missing_ok=True)

    def _update_volume(self):
        volume = max(0, min(100, int(self.settings.get("sound_volume", 35)))) / 100
        for effect in self.effects.values():
            effect.setVolume(volume)

    @classmethod
    def _ensure_sound(cls, name: str) -> Path:
        path = USER_DATA_DIR / f"ui-{name}-v{cls.SOUND_VERSION}.wav"
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        cls._write_sound(path, name)
        return path

    @staticmethod
    def _write_sound(path: Path, name: str):
        sample_rate = 44100
        durations = {
            "click": 0.065,
            "hover": 0.035,
            "navigate": 0.09,
            "switch": 0.075,
            "add": 0.12,
            "remove": 0.13,
            "open": 0.14,
            "save": 0.16,
            "export": 0.19,
            "confirm": 0.15,
        }
        frame_count = int(sample_rate * durations[name])
        frames = []

        for index in range(frame_count):
            t = index / sample_rate
            progress = index / frame_count
            attack = min(1.0, t / 0.004)
            envelope = attack * (1.0 - progress) ** 2.6

            if name == "click":
                tone = math.sin(2 * math.pi * (680 - 180 * progress) * t)
                transient = math.sin(2 * math.pi * 2600 * t) * max(0.0, 1 - t / 0.018)
                value = 0.72 * tone + 0.28 * transient
            elif name == "hover":
                value = math.sin(2 * math.pi * (930 + 80 * progress) * t) * 0.42
            elif name == "navigate":
                value = math.sin(2 * math.pi * (560 + 260 * progress) * t)
            elif name == "switch":
                value = math.sin(2 * math.pi * (720 + 130 * progress) * t) * 0.75
            elif name == "add":
                value = math.sin(2 * math.pi * (570 + 390 * progress) * t)
            elif name == "remove":
                value = math.sin(2 * math.pi * (520 - 260 * progress) * t)
            elif name == "open":
                value = math.sin(2 * math.pi * (470 + 360 * progress) * t)
            elif name == "save":
                frequency = 620 if progress < 0.45 else 830
                value = math.sin(2 * math.pi * frequency * t)
            elif name == "export":
                frequency = 520 + 520 * progress
                value = math.sin(2 * math.pi * frequency * t) * (0.75 + 0.25 * math.sin(math.pi * progress))
            elif name == "confirm":
                frequency = 620 if progress < 0.48 else 880
                local_envelope = 1.0 if progress < 0.48 else (1.0 - progress) / 0.52
                value = math.sin(2 * math.pi * frequency * t) * local_envelope

            sample = int(6200 * envelope * value)
            frames.append(struct.pack("<h", max(-32767, min(32767, sample))))

        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(b"".join(frames))

    @staticmethod
    def _sound_for_button(button: QPushButton) -> str:
        object_name = button.objectName()
        text = button.text().casefold()
        if object_name == "dangerButton" or "usuń" in text:
            return "remove"
        if "eksportuj" in text:
            return "export"
        if "zapisz" in text:
            return "save"
        if any(word in text for word in ("dodaj", "utwórz")):
            return "add"
        if any(word in text for word in ("otwórz", "wybierz")):
            return "open"
        if object_name == "primaryButton":
            return "confirm"
        if object_name == "wizardStep" or any(word in text for word in ("krok", "wróć", "menu")):
            return "navigate"
        return "click"

    def _play(self, name):
        if self.settings.get("sounds_enabled", True):
            self._update_volume()
            self.effects[name].play()

    def _animate_button(self, button, start_opacity):
        if not self.settings.get("animations_enabled", True):
            return
        previous = self.animations.pop(button, None)
        if previous:
            previous.stop()
            previous.deleteLater()
        effect = QGraphicsOpacityEffect(button)
        button.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(animation_duration(180))
        animation.setStartValue(start_opacity)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        def finish():
            if self.animations.get(button) is animation:
                self.animations.pop(button, None)
                try:
                    button.setGraphicsEffect(None)
                except RuntimeError:
                    pass
            animation.deleteLater()

        animation.finished.connect(finish)
        self.animations[button] = animation
        animation.start()

    def eventFilter(self, watched, event):
        if isinstance(watched, QPushButton) and watched.isEnabled():
            if event.type() == QEvent.Enter:
                now = time.monotonic()
                if self.settings.get("hover_sounds_enabled", False) and now - self._last_hover_sound > 0.08:
                    self._last_hover_sound = now
                    self._play("hover")
                self._animate_button(watched, 0.92)
            elif event.type() == QEvent.MouseButtonRelease:
                self._play(self._sound_for_button(watched))
                self._animate_button(watched, 0.72)
        elif isinstance(watched, QComboBox) and event.type() == QEvent.MouseButtonRelease and watched.isEnabled():
            self._play("switch")
        return super().eventFilter(watched, event)
