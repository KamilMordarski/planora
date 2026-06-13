from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_info import APP_DISCLAIMER, APP_NAME


class GuideDialog(QDialog):
    QUICK_START = [
        (
            "1. Przygotuj bibliotekę osób",
            "Otwórz „Bibliotekę osób” i dodaj nazwiska, których używasz. Lista jest wspólna dla wszystkich generatorów.",
        ),
        (
            "2. Utwórz pusty projekt",
            "Wybierz „Utwórz nowy grafik”, a następnie rodzaj dokumentu. Nowy projekt nie zawiera przykładowych dat ani przydziałów.",
        ),
        (
            "3. Przechodź przez kolejne kroki",
            "Przyciski u góry oraz „Poprzedni krok” i „Następny krok” pozwalają swobodnie wracać do każdej części projektu.",
        ),
        (
            "4. Dodaj daty i przydziały",
            "Najpierw dodaj tydzień, datę zebrania albo zebranie. Dopiero potem uzupełnij osoby, tematy i pozostałe szczegóły.",
        ),
        (
            "5. Sprawdź podgląd i ostrzeżenia",
            "Ostatni krok pokazuje dokument przed eksportem. W grafiku sprzątania sprawdź również panel kolizji obowiązków.",
        ),
        (
            "6. Zapisz projekt",
            "„Zapisz projekt” tworzy edytowalny plik JSON. To nie jest gotowy dokument, lecz plik do późniejszego kontynuowania pracy.",
        ),
        (
            "7. Eksportuj gotowy dokument",
            "PDF służy do drukowania i udostępniania, a JPG do szybkiego wysyłania jako obraz. Motyw aplikacji nie zmienia eksportu.",
        ),
    ]

    GENERATORS = [
        (
            "Wykład publiczny i Studium Strażnicy",
            "Dodaj każdy tydzień osobno. Wybierz typ standardowy albo wydarzenie specjalne, następnie przypisz osoby i tematy.",
        ),
        (
            "Sprzątanie, nagłośnienie i porządkowi",
            "Najpierw dodaj zakresy tygodniowe, później konkretne daty służby porządkowej. Panel kolizji ostrzeże o kilku obowiązkach tej samej osoby.",
        ),
        (
            "Plan zebrań w tygodniu",
            "Dodaj zebranie, uzupełnij jego dane, a potem utwórz sekcje i punkty programu. Wydarzenie specjalne może zawierać tytuł, podtytuł i obraz.",
        ),
    ]

    GOOD_PRACTICES = [
        (
            "Projekt a eksport",
            "Zachowaj plik JSON, jeśli plan może wymagać poprawek. PDF i JPG są dokumentami końcowymi i nie można ich ponownie edytować w aplikacji.",
        ),
        (
            "Bezpieczne aktualizacje",
            "Po Twoim potwierdzeniu aplikacja pobiera właściwy plik ZIP bezpośrednio na komputer. Nigdy nie podmienia uruchomionych plików automatycznie.",
        ),
        (
            "Prywatność danych",
            "Biblioteka osób i ustawienia są przechowywane lokalnie. Do internetu wysyłane jest tylko zapytanie o update.json podczas sprawdzania aktualizacji.",
        ),
        (
            "Rozwiązywanie problemów",
            "Gdy podgląd wygląda niepoprawnie, sprawdź puste daty i bardzo długie teksty. Projekt zapisz przed większymi zmianami.",
        ),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Poradnik — {APP_NAME}")
        self.resize(820, 720)

        root = QVBoxLayout(self)
        title = QLabel(f"Jak korzystać z {APP_NAME}")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Od pustego projektu do czytelnego PDF lub JPG.")
        subtitle.setObjectName("screenSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._cards_tab(self.QUICK_START), "Szybki start")
        tabs.addTab(self._cards_tab(self.GENERATORS), "Generatory")
        tabs.addTab(self._cards_tab(self.GOOD_PRACTICES), "Dobre praktyki")
        tabs.addTab(self._about_tab(), "O aplikacji")
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _cards_tab(cards: list[tuple[str, str]]) -> QScrollArea:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for heading, text in cards:
            content_layout.addWidget(GuideDialog._card(heading, text))
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _about_tab() -> QScrollArea:
        cards = [
            (
                "Niezależne i nieoficjalne narzędzie",
                APP_DISCLAIMER,
            ),
            (
                "Do czego służy Planora?",
                "Planora pomaga przygotowywać lokalne grafiki, kontrolować przydziały i eksportować dokumenty. Nie zastępuje oficjalnych źródeł informacji.",
            ),
            (
                "Aktualizacje online",
                "Planora korzysta ze stałego adresu update.json. Po wykryciu nowej wersji pobiera właściwą paczkę dla Windows lub macOS bez otwierania strony GitHub.",
            ),
        ]
        return GuideDialog._cards_tab(cards)

    @staticmethod
    def _card(heading: str, text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_title = QLabel(heading)
        card_title.setObjectName("cardTitle")
        card_text = QLabel(text)
        card_text.setWordWrap(True)
        card_layout.addWidget(card_title)
        card_layout.addWidget(card_text)
        return card
