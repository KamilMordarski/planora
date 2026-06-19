from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_hover: str
    accent_text: str
    danger: str
    success: str


THEMES = {
    "ocean": Theme(
        "Oceaniczny",
        "#eef4fb",
        "#ffffff",
        "#f5f8fc",
        "#14243a",
        "#61738a",
        "#d5deea",
        "#1769aa",
        "#10548a",
        "#ffffff",
        "#c03434",
        "#23835b",
    ),
    "graphite": Theme(
        "Grafitowy",
        "#171b22",
        "#222832",
        "#2b323e",
        "#f2f5f8",
        "#aab5c2",
        "#3c4654",
        "#7aa2f7",
        "#9ab8fa",
        "#10141b",
        "#ff7474",
        "#63d3a0",
    ),
    "forest": Theme(
        "Leśny",
        "#edf5f0",
        "#ffffff",
        "#f4f8f5",
        "#153129",
        "#627b72",
        "#d1e1d8",
        "#267558",
        "#195f45",
        "#ffffff",
        "#b83a3a",
        "#287d55",
    ),
    "plum": Theme(
        "Śliwkowy",
        "#f5f0f7",
        "#ffffff",
        "#faf7fb",
        "#302039",
        "#77647f",
        "#e2d5e7",
        "#7a3f8e",
        "#643275",
        "#ffffff",
        "#bd3c51",
        "#347b5e",
    ),
    "sand": Theme(
        "Piaskowy",
        "#f6f1e8",
        "#fffdf8",
        "#faf6ef",
        "#382d21",
        "#80705f",
        "#e5d9c8",
        "#a85e27",
        "#925322",
        "#ffffff",
        "#b64040",
        "#39795b",
    ),
    "porcelain": Theme(
        "Porcelanowy",
        "#f3f5f7",
        "#ffffff",
        "#f8f9fa",
        "#20262e",
        "#68717d",
        "#d9dee4",
        "#526579",
        "#3f5266",
        "#ffffff",
        "#bd3d45",
        "#2d7c5d",
    ),
    "lavender": Theme(
        "Lawendowy",
        "#f1f1fb",
        "#ffffff",
        "#f7f7fd",
        "#25253d",
        "#6c6b87",
        "#dadaec",
        "#6261a8",
        "#4e4d91",
        "#ffffff",
        "#bd4052",
        "#347b62",
    ),
    "mint": Theme(
        "Miętowy",
        "#edf7f5",
        "#ffffff",
        "#f5faf9",
        "#17332f",
        "#607c77",
        "#cfe3df",
        "#247b70",
        "#19675e",
        "#ffffff",
        "#b83e48",
        "#26795b",
    ),
    "midnight": Theme(
        "Nocny granat",
        "#0f1724",
        "#172235",
        "#1e2c42",
        "#edf4ff",
        "#9eb0c7",
        "#30415a",
        "#65a9e8",
        "#87bced",
        "#0e1825",
        "#ff7b83",
        "#66d1a4",
    ),
    "dark_forest": Theme(
        "Leśny",
        "#101b18",
        "#182823",
        "#20342d",
        "#edf8f3",
        "#a3bdb2",
        "#345247",
        "#62bc96",
        "#82cbaa",
        "#102018",
        "#ff7d82",
        "#70d5a4",
    ),
    "dark_plum": Theme(
        "Śliwkowy",
        "#1c1520",
        "#2a2030",
        "#35293c",
        "#f7eff9",
        "#c2adc8",
        "#4d3b55",
        "#c58bd3",
        "#d5a6df",
        "#211626",
        "#ff7d8e",
        "#70d2a6",
    ),
    "espresso": Theme(
        "Espresso",
        "#1d1815",
        "#2a231f",
        "#362d27",
        "#f7f1eb",
        "#c1afa1",
        "#514238",
        "#d49a68",
        "#e0ad80",
        "#211914",
        "#ff817d",
        "#76d19f",
    ),
}

LIGHT_THEME_KEYS = {"ocean", "forest", "plum", "sand", "porcelain", "lavender", "mint"}


def theme_options():
    light = [(key, f"Jasny · {value.name}") for key, value in THEMES.items() if key in LIGHT_THEME_KEYS]
    dark = [(key, f"Ciemny · {value.name}") for key, value in THEMES.items() if key not in LIGHT_THEME_KEYS]
    return light + dark


def responsive_scale_for_size(width: int, height: int) -> float:
    """Return a stable UI scale for windowed and compact application sizes."""
    if width < 760 or height < 560:
        return 0.78
    if width < 950 or height < 650:
        return 0.84
    if width < 1150 or height < 740:
        return 0.90
    if width < 1320 or height < 800:
        return 0.96
    return 1.0


def build_stylesheet(settings: dict) -> str:
    theme = THEMES.get(settings.get("theme"), THEMES["ocean"])
    accent = theme.accent
    responsive_scale = max(0.72, min(1.0, float(settings.get("responsive_scale", 1.0))))
    scale = max(80, min(140, int(settings.get("font_scale", 100)))) / 100 * responsive_scale
    density = {
        "compact": 0.78,
        "comfortable": 1.0,
        "spacious": 1.22,
    }.get(settings.get("interface_density"), 1.0) * responsive_scale
    radius = {
        "square": 2,
        "soft": 6,
        "rounded": 10,
    }.get(settings.get("corner_style"), 10)

    def px(value):
        return max(9, round(value * scale))

    def space(value):
        return max(2, round(value * density))

    return f"""
        QMainWindow, QDialog, QWidget {{
            background-color: {theme.background};
            color: {theme.text};
            font-family: "Segoe UI", "SF Pro Display", Arial;
            font-size: {px(13)}px;
        }}
        QWidget#startupSplash {{
            background-color: transparent;
        }}
        QFrame#splashCard {{
            background-color: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: 34px;
        }}
        QLabel#splashName {{
            color: {theme.text};
            font-size: {px(34)}px;
            font-weight: 800;
        }}
        QLabel#splashSubtitle {{
            color: {theme.muted};
            font-size: {px(14)}px;
        }}
        QLabel#splashFooter {{
            color: {theme.muted};
            font-size: {px(11)}px;
        }}
        QToolTip {{
            background: {theme.surface};
            color: {theme.text};
            border: 1px solid {theme.border};
            padding: 6px;
        }}
        QMenu, QMenuBar {{
            background: {theme.surface};
            color: {theme.text};
            border: 1px solid {theme.border};
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {accent};
            color: {theme.accent_text};
        }}
        QMenu::separator {{
            background: {theme.border};
            height: 1px;
            margin: 4px 8px;
        }}
        QLabel, QCheckBox, QRadioButton {{
            background-color: transparent;
            border: none;
        }}
        QPushButton {{
            background: {theme.surface};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            padding: {space(px(5))}px {space(px(10))}px;
            min-height: {px(16)}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme.surface_alt};
            border-color: {accent};
        }}
        QPushButton:pressed {{
            background: {theme.border};
            padding-top: {px(6)}px;
            padding-bottom: {px(4)}px;
        }}
        QPushButton:disabled {{
            color: {theme.muted};
            background: {theme.surface_alt};
        }}
        QPushButton#primaryButton {{
            background: {accent};
            color: {theme.accent_text};
            border-color: {accent};
        }}
        QPushButton#primaryButton:hover {{
            background: {theme.accent_hover};
            border-color: {theme.accent_hover};
        }}
        QPushButton#dangerButton {{
            color: {theme.danger};
            border-color: {theme.danger};
        }}
        QLabel#appName {{
            font-size: {px(34)}px;
            font-weight: 800;
        }}
        QLabel#heroSubtitle, QLabel#appInfo, QLabel#screenSubtitle {{
            color: {theme.muted};
        }}
        QLabel#screenTitle {{
            font-size: {px(28)}px;
            font-weight: 800;
            margin-top: 8px;
        }}
        QLabel#cardTitle {{
            font-size: {px(17)}px;
            font-weight: 750;
        }}
        QLabel#sectionTitle {{
            color: {accent};
            font-size: {px(14)}px;
            font-weight: 750;
        }}
        QLabel#guideBadge {{
            background-color: {theme.surface_alt};
            color: {accent};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            padding: {space(7)}px;
            font-weight: 700;
        }}
        QFrame#heroCard, QFrame#templateCard, QFrame#infoCard, QFrame#disclaimerCard {{
            background: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius + 6}px;
        }}
        QFrame#disclaimerCard {{
            border-left: 4px solid {accent};
        }}
        QFrame#templateCard:hover {{
            border: 2px solid {accent};
        }}
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QDateEdit,
        QSpinBox, QDoubleSpinBox, QTableWidget {{
            background: {theme.surface};
            color: {theme.text};
            selection-background-color: {accent};
            selection-color: {theme.accent_text};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            padding: {space(px(6))}px;
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
        QListWidget:focus, QDateEdit:focus {{
            border: 2px solid {accent};
        }}
        QListWidget::item {{
            background-color: transparent;
            color: {theme.text};
            border-radius: {radius}px;
            padding: {space(px(7))}px;
        }}
        QListWidget::item:hover {{
            background-color: {theme.surface_alt};
        }}
        QListWidget::item:selected {{
            background: {accent};
            color: {theme.accent_text};
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme.surface};
            color: {theme.text};
            border: 1px solid {theme.border};
            selection-background-color: {accent};
            selection-color: {theme.accent_text};
            outline: none;
        }}
        QComboBox QLineEdit {{
            background-color: transparent;
            color: {theme.text};
            selection-background-color: {accent};
            selection-color: {theme.accent_text};
            border: none;
            border-radius: 0;
            padding: 0 5px;
            min-height: 0;
        }}
        QTableWidget QComboBox {{
            margin: 3px;
            min-height: {px(22)}px;
        }}
        QHeaderView::section {{
            background: {theme.surface_alt};
            color: {theme.text};
            border: none;
            border-right: 1px solid {theme.border};
            border-bottom: 1px solid {theme.border};
            padding: {space(px(6))}px;
            font-weight: 700;
        }}
        QTableCornerButton::section {{
            background: {theme.surface_alt};
            border: 1px solid {theme.border};
        }}
        QCalendarWidget QWidget {{
            alternate-background-color: {theme.surface_alt};
        }}
        QCalendarWidget QAbstractItemView:enabled {{
            background: {theme.surface};
            color: {theme.text};
            selection-background-color: {accent};
            selection-color: {theme.accent_text};
        }}
        QCalendarWidget QToolButton {{
            background: transparent;
            color: {theme.text};
            border: none;
        }}
        QTabWidget::pane {{
            background: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: {theme.surface_alt};
            color: {theme.muted};
            padding: {space(px(6))}px {space(px(10))}px;
            border: 1px solid {theme.border};
            border-bottom: none;
            border-top-left-radius: {radius}px;
            border-top-right-radius: {radius}px;
        }}
        QTabBar::tab:selected {{
            background: {theme.surface};
            color: {accent};
            font-weight: 700;
        }}
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 11px;
            margin: 2px;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 11px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {theme.border};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:horizontal {{
            background: {theme.border};
            border-radius: 5px;
            min-width: 30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QCheckBox::indicator {{
            width: {px(17)}px;
            height: {px(17)}px;
        }}
        QSlider::groove:horizontal {{
            background: {theme.border};
            height: 5px;
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {theme.surface};
            border: 2px solid {accent};
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        QProgressBar {{
            background: {theme.surface_alt};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background: {accent};
            border-radius: {radius}px;
        }}
        QGroupBox {{
            background-color: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            margin-top: 14px;
            padding: {space(13)}px {space(8)}px {space(8)}px {space(8)}px;
            font-weight: 700;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            color: {accent};
        }}
        QGroupBox QLabel, QGroupBox QCheckBox, QGroupBox QRadioButton {{
            background-color: transparent;
        }}
        QFrame#editorToolbar, QWidget#editorToolbar, QWidget#editorContextBar {{
            background-color: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius + 2}px;
        }}
        QFrame#wizardHeader, QFrame#wizardFooter {{
            background-color: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius + 2}px;
        }}
        QLabel#documentPreviewPage {{
            background-color: #ffffff;
            border: 1px solid {theme.border};
        }}
        QPushButton#wizardStep {{
            background-color: transparent;
            color: {theme.muted};
            border: none;
            border-radius: {radius}px;
            padding: {space(px(6))}px {space(px(9))}px;
        }}
        QPushButton#wizardStep:hover {{
            background-color: {theme.surface_alt};
            color: {theme.text};
        }}
        QPushButton#wizardStep:checked {{
            background-color: {accent};
            color: {theme.accent_text};
        }}
        QPushButton#wizardStep[complete="true"] {{
            color: {accent};
        }}
        QLabel#helpText {{
            color: {theme.muted};
            background-color: transparent;
        }}
        QLabel#appInfo a {{
            color: {accent};
            text-decoration: none;
        }}
        QSplitter::handle {{
            background: {theme.border};
            width: 2px;
            height: 2px;
        }}
    """
