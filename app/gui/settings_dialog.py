from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import UPDATE_URL, USER_DATA_DIR
from app.gui.responsive import configure_form
from app.gui.theme_manager import THEMES, theme_options
from app.gui.ui_feedback import UiFeedback


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia aplikacji")
        self.resize(650, 500)

        layout = QVBoxLayout(self)
        title = QLabel("Dostosuj aplikację do siebie")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Zmiany dotyczą wyłącznie interfejsu. Wygląd eksportowanych dokumentów pozostaje bez zmian.")
        subtitle.setObjectName("screenSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._appearance_tab(settings), "Wygląd")
        tabs.addTab(self._behavior_tab(settings), "Zachowanie")
        tabs.addTab(self._updates_tab(settings), "Aktualizacje")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _appearance_tab(self, settings):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        theme_group = QGroupBox("Motyw kolorystyczny")
        form = configure_form(QFormLayout(theme_group))
        self.theme = QComboBox()
        for key, label in theme_options():
            self.theme.addItem(label, key)
        index = self.theme.findData(settings.get("theme", "ocean"))
        self.theme.setCurrentIndex(max(0, index))

        self.accent_color = QLineEdit(settings.get("accent_color", ""))
        self.accent_color.setPlaceholderText("Domyślny kolor motywu")
        choose_color = QPushButton("Wybierz kolor")
        choose_color.clicked.connect(self.choose_accent)
        color_row = QHBoxLayout()
        color_row.addWidget(self.accent_color)
        color_row.addWidget(choose_color)
        form.addRow("Gotowy motyw:", self.theme)
        form.addRow("Własny kolor akcentu:", color_row)
        layout.addWidget(theme_group)

        font_group = QGroupBox("Rozmiar interfejsu")
        font_layout = configure_form(QFormLayout(font_group))
        self.font_scale = QSlider(Qt.Horizontal)
        self.font_scale.setRange(80, 140)
        self.font_scale.setTickInterval(10)
        self.font_scale.setValue(int(settings.get("font_scale", 100)))
        self.font_value = QLabel()
        self.font_scale.valueChanged.connect(lambda value: self.font_value.setText(f"{value}%"))
        self.font_value.setText(f"{self.font_scale.value()}%")
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_scale)
        font_row.addWidget(self.font_value)
        font_layout.addRow("Skala tekstu i kontrolek:", font_row)
        layout.addWidget(font_group)

        note = QFrame()
        note.setObjectName("infoCard")
        note_layout = QVBoxLayout(note)
        note_title = QLabel("Eksport pozostaje niezależny")
        note_title.setObjectName("sectionTitle")
        note_text = QLabel(
            "PDF i JPG nadal będą białe z czarnym tekstem. Plan zebrań w tygodniu zachowa własne kolorowe sekcje."
        )
        note_text.setWordWrap(True)
        note_layout.addWidget(note_title)
        note_layout.addWidget(note_text)
        layout.addWidget(note)
        layout.addStretch()
        return tab

    def _behavior_tab(self, settings):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("Efekty interfejsu")
        group_layout = QVBoxLayout(group)
        self.animations = QCheckBox("Animuj przejścia pomiędzy ekranami")
        self.animations.setChecked(bool(settings.get("animations_enabled", True)))
        self.sounds = QCheckBox("Odtwarzaj subtelne dźwięki kliknięć")
        self.sounds.setChecked(bool(settings.get("sounds_enabled", True)))
        group_layout.addWidget(self.animations)
        group_layout.addWidget(self.sounds)
        sound_row = QHBoxLayout()
        self.sound_volume = QSlider(Qt.Horizontal)
        self.sound_volume.setRange(0, 100)
        self.sound_volume.setValue(int(settings.get("sound_volume", 35)))
        self.sound_value = QLabel(f"{self.sound_volume.value()}%")
        self.sound_volume.valueChanged.connect(lambda value: self.sound_value.setText(f"{value}%"))
        test_sound = QPushButton("Odtwórz dźwięk testowy")
        self.sound_preview = QSoundEffect(self)
        self.sound_preview.setSource(QUrl.fromLocalFile(str(UiFeedback._ensure_sound("click"))))
        test_sound.clicked.connect(self.preview_sound)
        sound_row.addWidget(self.sound_volume, 1)
        sound_row.addWidget(self.sound_value)
        sound_row.addWidget(test_sound)
        group_layout.addWidget(QLabel("Głośność dźwięków:"))
        group_layout.addLayout(sound_row)
        layout.addWidget(group)
        layout.addStretch()
        return tab

    def preview_sound(self):
        self.sound_preview.setVolume(self.sound_volume.value() / 100)
        self.sound_preview.play()

    def _updates_tab(self, settings):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("Zdalne aktualizacje")
        form = configure_form(QFormLayout(group))
        self.update_url = QLineEdit(UPDATE_URL)
        self.update_url.setReadOnly(True)
        self.check_on_start = QCheckBox("Sprawdzaj aktualizacje przy uruchomieniu")
        self.check_on_start.setChecked(bool(settings.get("check_updates_on_start", False)))
        data_dir = QLabel(str(USER_DATA_DIR))
        data_dir.setWordWrap(True)
        form.addRow("Adres update.json:", self.update_url)
        form.addRow("", self.check_on_start)
        form.addRow("Katalog danych:", data_dir)
        layout.addWidget(group)
        warning = QLabel(
            "Adres aktualizacji jest ustawiony przez autora aplikacji. "
            "Nie należy go zmieniać, ponieważ nieprawidłowy adres może zepsuć sprawdzanie aktualizacji."
        )
        warning.setObjectName("helpText")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addStretch()
        return tab

    def choose_accent(self):
        fallback = THEMES.get(self.theme.currentData(), THEMES["ocean"]).accent
        color = QColorDialog.getColor(QColor(self.accent_color.text() or fallback), self, "Wybierz kolor akcentu")
        if color.isValid():
            self.accent_color.setText(color.name())

    def values(self) -> dict:
        accent = self.accent_color.text().strip()
        if accent and not QColor(accent).isValid():
            accent = ""
        return {
            "theme": self.theme.currentData(),
            "accent_color": accent,
            "font_scale": self.font_scale.value(),
            "animations_enabled": self.animations.isChecked(),
            "sounds_enabled": self.sounds.isChecked(),
            "sound_volume": self.sound_volume.value(),
            "update_url": UPDATE_URL,
            "check_updates_on_start": self.check_on_start.isChecked(),
        }
