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
from app.gui.responsive import configure_form, fit_window_to_screen, scrollable_widget
from app.gui.theme_manager import theme_options
from app.gui.ui_feedback import UiFeedback


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.tutorials_completed = list(settings.get("tutorials_completed", []))
        self.setWindowTitle("Ustawienia aplikacji")
        fit_window_to_screen(self, 650, 600, 440, 360)

        layout = QVBoxLayout(self)
        title = QLabel("Dostosuj aplikację do siebie")
        title.setObjectName("screenTitle")
        subtitle = QLabel(
            "Zmiany wyglądu interfejsu są niezależne od eksportu. Osobne ustawienia drukowania "
            "działają tylko dla przycisku „Drukuj”."
        )
        subtitle.setObjectName("screenSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(scrollable_widget(self._appearance_tab(settings)), "Wygląd")
        tabs.addTab(scrollable_widget(self._printing_tab(settings)), "Drukowanie")
        tabs.addTab(scrollable_widget(self._behavior_tab(settings)), "Zachowanie")
        tabs.addTab(scrollable_widget(self._updates_tab(settings)), "Aktualizacje")
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
        self.font_value = QLabel(f"{self.font_scale.value()}%")
        self.font_scale.valueChanged.connect(lambda value: self.font_value.setText(f"{value}%"))
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

    def _printing_tab(self, settings):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Bezpośrednie drukowanie")
        form = configure_form(QFormLayout(group))
        help_text = QLabel(
            "Te opcje działają tylko dla przycisku „Drukuj”. Eksport PDF/JPG pozostaje zgodny z szablonem."
        )
        help_text.setObjectName("helpText")
        help_text.setWordWrap(True)

        self.print_text_weight = QComboBox()
        self.print_text_weight.addItem("Normalny tekst", "normal")
        self.print_text_weight.addItem("Lekko pogrubiony", "bold")
        self.print_text_weight.addItem("Mocno pogrubiony", "extra_bold")
        weight_index = self.print_text_weight.findData(settings.get("print_text_weight", "normal"))
        self.print_text_weight.setCurrentIndex(max(0, weight_index))

        self.print_contrast = QSlider(Qt.Horizontal)
        self.print_contrast.setRange(80, 150)
        self.print_contrast.setTickInterval(10)
        self.print_contrast.setValue(int(settings.get("print_contrast", 100)))
        self.print_contrast_value = QLabel(f"{self.print_contrast.value()}%")
        self.print_contrast.valueChanged.connect(lambda value: self.print_contrast_value.setText(f"{value}%"))
        contrast_row = QHBoxLayout()
        contrast_row.addWidget(self.print_contrast, 1)
        contrast_row.addWidget(self.print_contrast_value)

        self.print_scale = QSlider(Qt.Horizontal)
        self.print_scale.setRange(80, 100)
        self.print_scale.setTickInterval(5)
        self.print_scale.setValue(int(settings.get("print_scale", 100)))
        self.print_scale_value = QLabel(f"{self.print_scale.value()}%")
        self.print_scale.valueChanged.connect(lambda value: self.print_scale_value.setText(f"{value}%"))
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.print_scale, 1)
        scale_row.addWidget(self.print_scale_value)

        self.print_grayscale = QCheckBox("Drukuj w skali szarości")
        self.print_grayscale.setChecked(bool(settings.get("print_grayscale", False)))
        self.print_smooth_scaling = QCheckBox("Wygładzaj dokument podczas dopasowania do strony")
        self.print_smooth_scaling.setChecked(bool(settings.get("print_smooth_scaling", True)))

        form.addRow("", help_text)
        form.addRow("Grubość tekstu:", self.print_text_weight)
        form.addRow("Kontrast wydruku:", contrast_row)
        form.addRow("Skala na stronie:", scale_row)
        form.addRow("", self.print_grayscale)
        form.addRow("", self.print_smooth_scaling)
        layout.addWidget(group)

        note = QFrame()
        note.setObjectName("infoCard")
        note_layout = QVBoxLayout(note)
        note_title = QLabel("Do szybkiej korekty wydruku")
        note_title.setObjectName("sectionTitle")
        note_text = QLabel(
            "Jeśli drukarka robi zbyt cienki tekst, wybierz pogrubienie i lekko podbij kontrast. "
            "Jeśli ucina krawędzie, zmniejsz skalę do 95% albo 90%."
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
        self.tutorials = QCheckBox("Pokazuj samouczek przy pierwszym użyciu generatora")
        self.tutorials.setChecked(bool(settings.get("tutorials_enabled", True)))
        group_layout.addWidget(self.animations)
        group_layout.addWidget(self.startup_splash)
        group_layout.addWidget(self.sounds)
        group_layout.addWidget(self.hover_sounds)
        group_layout.addWidget(self.tutorials)

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
            "Jeśli automatyczna podmiana programu nie jest możliwa, Planora pozwoli pobrać gotowy plik EXE ręcznie."
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
            "tutorials_enabled": self.tutorials.isChecked(),
            "tutorials_completed": self.tutorials_completed,
            "print_text_weight": self.print_text_weight.currentData(),
            "print_contrast": self.print_contrast.value(),
            "print_scale": self.print_scale.value(),
            "print_grayscale": self.print_grayscale.isChecked(),
            "print_smooth_scaling": self.print_smooth_scaling.isChecked(),
            "update_url": UPDATE_URL,
            "check_updates_on_start": self.check_on_start.isChecked(),
        }
