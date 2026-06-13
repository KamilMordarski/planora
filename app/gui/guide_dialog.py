from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
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
            "Otwórz „Bibliotekę osób”. Dodaj nazwiska ręcznie albo użyj przycisku „Importuj listę JSON”. "
            "Ta sama lista jest dostępna we wszystkich generatorach.",
        ),
        (
            "2. Utwórz pusty projekt",
            "Na ekranie głównym wybierz „Utwórz nowy grafik”, a następnie rodzaj dokumentu. "
            "Nowe projekty nie zawierają przykładowych dat, nazwisk ani nazwy zboru.",
        ),
        (
            "3. Pracuj krok po kroku",
            "Każdy edytor dzieli pracę na krótkie etapy. Możesz używać przycisków kroków u góry "
            "albo przycisków „Poprzedni krok” i „Następny krok”.",
        ),
        (
            "4. Kontroluj podgląd",
            "Ostatni krok pokazuje gotowy dokument. Powiększ podgląd, dopasuj stronę i popraw "
            "zbyt długie teksty przed eksportem.",
        ),
        (
            "5. Zapisz i eksportuj",
            "Zapis projektu tworzy edytowalny plik JSON. Eksport PDF służy do druku, a JPG "
            "do łatwego wysyłania gotowego planu.",
        ),
    ]

    PEOPLE = [
        (
            "Wspólna biblioteka",
            "Nazwisko dodane do biblioteki pojawi się w polach wyboru każdego generatora. "
            "Zmiany są zapisywane lokalnie dopiero po zatwierdzeniu okna przyciskiem OK.",
        ),
        (
            "Import listy JSON",
            "Import dodaje nowe osoby do istniejącej biblioteki, nie usuwa obecnych wpisów "
            "i pomija duplikaty bez względu na wielkość liter.",
        ),
        (
            "Obsługiwane formaty",
            'Najprostszy plik ma postać ["Jan Kowalski", "Anna Nowak"]. Możesz też użyć obiektu '
            'w postaci {"people": ["Jan Kowalski", "Anna Nowak"]}.',
        ),
        (
            "Porządkowanie listy",
            "Użyj wyszukiwarki, aby szybko znaleźć osobę. Zaznacz wpis, zmień nazwisko albo usuń "
            "je z biblioteki. Usunięcie nie zmienia już zapisanych projektów.",
        ),
    ]

    GENERATORS = [
        (
            "Wykład publiczny i Studium Strażnicy",
            "Dodaj każdy tydzień osobno. Wybierz standardowy tydzień albo wydarzenie specjalne, "
            "a następnie przypisz osoby, tytuły i pozostałe informacje.",
        ),
        (
            "Sprzątanie, nagłośnienie i porządkowi",
            "Dodaj zakresy tygodniowe i konkretne daty służby porządkowej. Panel kolizji ostrzega, "
            "gdy ta sama osoba ma kilka obowiązków tego samego dnia.",
        ),
        (
            "Plan zebrań w tygodniu",
            "Dodaj zebranie, sekcje i punkty programu. Możesz zmieniać kolory sekcji oraz dodać "
            "wydarzenie specjalne z tytułem, podtytułem i obrazem. W podglądzie i eksporcie "
            "punkty są automatycznie numerowane od pierwszego punktu po uwagach wstępnych. "
            "Górny pasek przełącza dni bez wracania do listy, a duplikowanie zebrania ustawia "
            "datę tydzień później. Standardowe sekcje można dodać jednym kliknięciem.",
        ),
        (
            "Plan grup służby",
            "Wpisz własny nagłówek, ustaw liczbę i kolejność grup, potem wybierz osoby z biblioteki. "
            "Nowa osoba jest członkiem grupy; grupowy i asystent są wyróżniani w eksporcie.",
        ),
    ]

    FILES = [
        (
            "Projekt JSON",
            "Plik projektu zachowuje wszystkie pola potrzebne do dalszej edycji. Zapisuj go przed "
            "większymi zmianami i otwieraj później przyciskiem „Otwórz projekt”.",
        ),
        (
            "PDF i JPG",
            "PDF jest najlepszy do drukowania. JPG jest wygodny do wysłania jako obraz. "
            "Motyw i rozmiar interfejsu nie zmieniają wyglądu eksportu.",
        ),
        (
            "Dokumenty wielostronicowe",
            "Gdy plan grup nie mieści się na jednej stronie, Planora automatycznie tworzy kolejne "
            "strony PDF i osobne pliki JPG oznaczone numerem strony.",
        ),
        (
            "Prywatność danych",
            "Biblioteka osób, projekty i ustawienia pozostają na Twoim urządzeniu. Do internetu "
            "wysyłane jest jedynie zapytanie o dostępność aktualizacji.",
        ),
    ]

    SETTINGS_AND_HELP = [
        (
            "Personalizacja",
            "W ustawieniach zmienisz motyw, kolor akcentu, skalę tekstu, gęstość interfejsu i "
            "kształt kontrolek. Eksportowane pliki zachowują swój ustalony wygląd.",
        ),
        (
            "Animacje i dźwięki",
            "Możesz osobno wyłączyć animacje, logo startowe, wszystkie dźwięki lub dźwięki po "
            "najechaniu. Dostępna jest też regulacja szybkości animacji i głośności.",
        ),
        (
            "Bezpieczne aktualizacje",
            "Po Twoim potwierdzeniu Planora pobiera właściwą paczkę, zamyka się, instaluje nową "
            "wersję i uruchamia ponownie. Przed aktualizacją zapisz otwarty projekt.",
        ),
        (
            "Gdy coś wygląda źle",
            "Sprawdź puste daty, bardzo długie teksty i podgląd ostatniego kroku. Jeśli problem "
            "pojawił się po zmianie wyglądu, wróć do motywu Oceanicznego i skali 100%.",
        ),
        (
            "Informacja o aplikacji",
            APP_DISCLAIMER,
        ),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Poradnik — {APP_NAME}")
        self.resize(940, 760)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.addWidget(self._hero())

        tabs = QTabWidget()
        tabs.addTab(self._cards_tab(self.QUICK_START, "Najkrótsza droga od pustego projektu do eksportu."), "Start")
        tabs.addTab(self._cards_tab(self.PEOPLE, "Jedna lista nazwisk dla całej aplikacji."), "Lista osób")
        tabs.addTab(self._cards_tab(self.GENERATORS, "Każdy generator prowadzi przez własne kroki."), "Generatory")
        tabs.addTab(self._cards_tab(self.FILES, "Co zapisywać i który format wybrać."), "Pliki i eksport")
        tabs.addTab(
            self._cards_tab(self.SETTINGS_AND_HELP, "Dostosowanie aplikacji i szybka pomoc."),
            "Ustawienia i pomoc",
        )
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _hero() -> QFrame:
        hero = QFrame()
        hero.setObjectName("heroCard")
        layout = QVBoxLayout(hero)
        title = QLabel(f"Poznaj {APP_NAME}")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Przejrzysty przewodnik po projektach, osobach, eksporcie i ustawieniach.")
        subtitle.setObjectName("screenSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        facts = QHBoxLayout()
        for text in ("4 generatory", "PDF i JPG", "Lokalne dane", "Aktualizacje online"):
            label = QLabel(text)
            label.setObjectName("guideBadge")
            label.setAlignment(Qt.AlignCenter)
            facts.addWidget(label)
        layout.addLayout(facts)
        return hero

    @staticmethod
    def _cards_tab(cards: list[tuple[str, str]], intro: str) -> QScrollArea:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        intro_label = QLabel(intro)
        intro_label.setObjectName("screenSubtitle")
        intro_label.setWordWrap(True)
        content_layout.addWidget(intro_label)
        for heading, text in cards:
            content_layout.addWidget(GuideDialog._card(heading, text))
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _card(heading: str, text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_title = QLabel(heading)
        card_title.setObjectName("cardTitle")
        card_text = QLabel(text)
        card_text.setObjectName("helpText")
        card_text.setWordWrap(True)
        card_layout.addWidget(card_title)
        card_layout.addWidget(card_text)
        return card
