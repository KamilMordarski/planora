from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QCheckBox,
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
from app.gui.theme_manager import theme_options
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

        theme_help = QLabel("Gotowe motywy mają dobrane kolory tekstu, tła i akcentów dla dobrej czytelności.")
        theme_help.setObjectName("helpText")
        theme_help.setWordWrap(True)
        form.addRow("Motyw interfejsu:", self.theme)
        form.addRow("", theme_help)
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

        self.interface_density = QComboBox()
        self.interface_density.addItem("Kompaktowa", "compact")
        self.interface_density.addItem("Wygodna", "comfortable")
        self.interface_density.addItem("Przestronna", "spacious")
        density_index = self.interface_density.findData(settings.get("interface_density", "comfortable"))
        self.interface_density.setCurrentIndex(max(0, density_index))

        self.corner_style = QComboBox()
        self.corner_style.addItem("Proste", "square")
        self.corner_style.addItem("Subtelnie zaokrąglone", "soft")
        self.corner_style.addItem("Zaokrąglone", "rounded")
        corner_index = self.corner_style.findData(settings.get("corner_style", "rounded"))
        self.corner_style.setCurrentIndex(max(0, corner_index))
        font_layout.addRow("Gęstość interfejsu:", self.interface_density)
        font_layout.addRow("Kształt kontrolek:", self.corner_style)
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
        self.startup_splash = QCheckBox("Pokazuj animowane logo przy uruchomieniu")
        self.startup_splash.setChecked(bool(settings.get("startup_splash_enabled", True)))
        self.sounds = QCheckBox("Odtwarzaj subtelne dźwięki interfejsu")
        self.sounds.setChecked(bool(settings.get("sounds_enabled", True)))
        self.hover_sounds = QCheckBox("Odtwarzaj dźwięk po najechaniu na przycisk")
        self.hover_sounds.setChecked(bool(settings.get("hover_sounds_enabled", False)))
        group_layout.addWidget(self.animations)
        group_layout.addWidget(self.startup_splash)
        group_layout.addWidget(self.sounds)
        group_layout.addWidget(self.hover_sounds)

        animation_row = QHBoxLayout()
        self.animation_speed = QSlider(Qt.Horizontal)
        self.animation_speed.setRange(50, 180)
        self.animation_speed.setTickInterval(10)
        self.animation_speed.setValue(int(settings.get("animation_speed", 100)))
        self.animation_value = QLabel(f"{self.animation_speed.value()}%")
        self.animation_speed.valueChanged.connect(lambda value: self.animation_value.setText(f"{value}%"))
        animation_row.addWidget(self.animation_speed, 1)
        animation_row.addWidget(self.animation_value)
        group_layout.addWidget(QLabel("Szybkość animacji:"))
        group_layout.addLayout(animation_row)

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
            "Nie należy go zmieniać, ponieważ nieprawidłowy adres może zepsuć sprawdzanie aktualizacji. "
            "Po Twoim potwierdzeniu gotowa aplikacja może automatycznie zainstalować nową wersję i uruchomić się ponownie."
        )
        warning.setObjectName("helpText")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addStretch()
        return tab

    def values(self) -> dict:
        return {
            "theme": self.theme.currentData(),
            "font_scale": self.font_scale.value(),
            "interface_density": self.interface_density.currentData(),
            "corner_style": self.corner_style.currentData(),
            "animations_enabled": self.animations.isChecked(),
            "animation_speed": self.animation_speed.value(),
            "startup_splash_enabled": self.startup_splash.isChecked(),
            "sounds_enabled": self.sounds.isChecked(),
            "hover_sounds_enabled": self.hover_sounds.isChecked(),
            "sound_volume": self.sound_volume.value(),
            "update_url": UPDATE_URL,
            "check_updates_on_start": self.check_on_start.isChecked(),
        }
