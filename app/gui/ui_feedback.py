import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QPushButton

from app.config import USER_DATA_DIR


class UiFeedback(QObject):
    SOUND_VERSION = 2

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.effects: dict[str, QSoundEffect] = {}
        for name in ("click", "navigate", "confirm", "warning"):
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(str(self._ensure_sound(name))))
            self.effects[name] = effect
        self._update_volume()

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
        durations = {"click": 0.065, "navigate": 0.09, "confirm": 0.15, "warning": 0.14}
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
            elif name == "navigate":
                value = math.sin(2 * math.pi * (560 + 260 * progress) * t)
            elif name == "confirm":
                frequency = 620 if progress < 0.48 else 880
                local_envelope = 1.0 if progress < 0.48 else (1.0 - progress) / 0.52
                value = math.sin(2 * math.pi * frequency * t) * local_envelope
            else:
                frequency = 310 if progress < 0.5 else 245
                value = math.sin(2 * math.pi * frequency * t)

            sample = int(7200 * envelope * value)
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
            return "warning"
        if object_name == "primaryButton" or any(word in text for word in ("zapisz", "eksportuj", "utwórz")):
            return "confirm"
        if object_name == "wizardStep" or any(word in text for word in ("krok", "wróć", "menu")):
            return "navigate"
        return "click"

    def eventFilter(self, watched, event):
        if (
            self.settings.get("sounds_enabled", True)
            and isinstance(watched, QPushButton)
            and event.type() == QEvent.MouseButtonRelease
            and watched.isEnabled()
        ):
            self._update_volume()
            self.effects[self._sound_for_button(watched)].play()
        return super().eventFilter(watched, event)
