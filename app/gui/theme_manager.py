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
        "#b0672d",
        "#925322",
        "#ffffff",
        "#b64040",
        "#39795b",
    ),
}


def theme_options():
    return [(key, value.name) for key, value in THEMES.items()]


def build_stylesheet(settings: dict) -> str:
    theme = THEMES.get(settings.get("theme"), THEMES["ocean"])
    accent = settings.get("accent_color") or theme.accent
    scale = max(80, min(140, int(settings.get("font_scale", 100)))) / 100
    density = {
        "compact": 0.78,
        "comfortable": 1.0,
        "spacious": 1.22,
    }.get(settings.get("interface_density"), 1.0)
    radius = {
        "square": 2,
        "soft": 6,
        "rounded": 10,
    }.get(settings.get("corner_style"), 10)

    def px(value):
        return max(10, round(value * scale))

    def space(value):
        return max(3, round(value * density))

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
        QToolTip {{
            background: {theme.surface};
            color: {theme.text};
            border: 1px solid {theme.border};
            padding: 6px;
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
            padding: {space(px(8))}px {space(px(15))}px;
            min-height: {px(20)}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme.surface_alt};
            border-color: {accent};
        }}
        QPushButton:pressed {{
            background: {theme.border};
            padding-top: {px(9)}px;
            padding-bottom: {px(7)}px;
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
        QTabWidget::pane {{
            background: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: {theme.surface_alt};
            color: {theme.muted};
            padding: {space(px(9))}px {space(px(14))}px;
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
        QScrollBar::handle:vertical {{
            background: {theme.border};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QCheckBox::indicator {{
            width: {px(17)}px;
            height: {px(17)}px;
        }}
        QGroupBox {{
            background-color: {theme.surface};
            border: 1px solid {theme.border};
            border-radius: {radius}px;
            margin-top: 14px;
            padding: {space(16)}px {space(10)}px {space(10)}px {space(10)}px;
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
        QFrame#editorToolbar, QWidget#editorToolbar {{
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
            padding: {space(px(9))}px {space(px(13))}px;
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
