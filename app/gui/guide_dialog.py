from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_info import APP_DISCLAIMER, APP_NAME
from app.core.wol_importer import JW_MEETINGS_BASE_URL


class GuideDialog(QDialog):
    QUICK_START = [
        (
            "1. Przygotuj bibliotekę osób",
            "Otwórz „Bibliotekę osób i role”. Dodaj nazwiska ręcznie albo użyj przycisku „Importuj listę JSON”. "
            "Zaznacz, kto może prowadzić zbiórkę, obsługiwać konsolę, mikrofony i wykonywać inne zadania.",
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
            "4. Dodawaj od razu wypełnione terminy",
            "Wpisz informacje w formularzu, a następnie wybierz „Dodaj z formularza”. Gdy w projekcie są już terminy, "
            "najpierw użyj „Nowy formularz”, aby przygotować kolejny wpis bez zmieniania obecnego.",
        ),
        (
            "5. Kontroluj podgląd",
            "Ostatni krok pokazuje gotowy dokument. Powiększ podgląd, dopasuj stronę i popraw "
            "zbyt długie teksty przed eksportem.",
        ),
        (
            "6. Zapisz i eksportuj",
            "Zapis projektu tworzy edytowalny plik JSON. Możesz od razu użyć przycisku „Drukuj”, "
            "wyeksportować PDF do późniejszego druku albo JPG do łatwego wysyłania gotowego planu.",
        ),
    ]

    JW_IMPORT = [
        (
            "1. Otwórz stronę spotkań JW",
            "Kliknij przycisk poniżej. Otworzy się strona wol.jw.org/pl/wol/meetings/r12/lp-p/, "
            "na której wybierzesz interesujący Cię tydzień.",
        ),
        (
            "2. Wybierz tydzień",
            "Na stronie JW przejdź do tygodnia, który chcesz dodać. Pełny adres powinien kończyć się "
            "rokiem i numerem tygodnia, na przykład /2026/24.",
        ),
        (
            "3. Skopiuj pełny adres",
            "Kliknij pasek adresu przeglądarki i skopiuj cały link do wybranego tygodnia. "
            "Nie kopiuj adresu pojedynczego artykułu ani samego fragmentu strony.",
        ),
        (
            "4. Wklej adres w Planorze",
            "Otwórz generator „Plan zebrań w tygodniu”, przejdź do kroku „Program” i kliknij "
            "„Wklej adres JW…”. Wklej skopiowany link i zatwierdź.",
        ),
        (
            "5. Uzupełnij przydziały",
            "Planora utworzy nowe zwykłe zebranie z datą środy oraz pobranymi sekcjami i punktami. "
            "Nazwiska pozostają puste, dzięki czemu możesz przypisać osoby z własnej biblioteki.",
        ),
        (
            "Bieżący tydzień",
            "Jeżeli potrzebujesz programu na obecny tydzień, użyj przycisku „Bieżący tydzień z JW”. "
            "Nie trzeba wtedy kopiować żadnego adresu.",
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
            "Import dodaje nowe osoby do istniejącej biblioteki, nie usuwa obecnych wpisów i pomija duplikaty "
            "bez względu na wielkość liter. Plik wyeksportowany przez Planorę odtwarza role i możliwe przydziały.",
        ),
        (
            "Eksport listy JSON",
            "Przycisk „Eksportuj listę JSON” zapisuje nazwiska oraz przypisane role w jednym przenośnym pliku. "
            "Możesz użyć go jako kopii zapasowej albo przenieść kompletną bibliotekę na inny komputer.",
        ),
        (
            "Obsługiwane formaty",
            'Najprostszy plik ma postać ["Jan Kowalski", "Anna Nowak"]. Możesz też użyć obiektu '
            'w postaci {"people": ["Jan Kowalski", "Anna Nowak"]}. Format eksportowany przez Planorę zawiera '
            'obiekty z polami "name" i "roles".',
        ),
        (
            "Porządkowanie listy",
            "Role są widoczne bezpośrednio pod nazwiskiem na liście. Użyj wyszukiwarki oraz filtrów roli "
            "i możliwego przydziału, aby szybko znaleźć odpowiednie osoby. Usunięcie osoby nie zmienia już zapisanych projektów.",
        ),
        (
            "Role i możliwe przydziały",
            "Role osoby obejmują starszego, sługę pomocniczego i rodzaje pionierów. Pionier pomocniczy może mieć "
            "datę końcową i wtedy rola wygaśnie automatycznie. Osobno zaznacz możliwe przydziały, dzięki którym "
            "listy podpowiadają lektorów, prowadzących, konsolę, mikrofony, porządkowych, uczestników i modlitwy. "
            "W wyjątkowej sytuacji możesz ręcznie wpisać inną osobę; taki przydział zostanie zachowany.",
        ),
    ]

    PLANNING = [
        (
            "Asystent układania grafików",
            "Na ekranie głównym wybierz „Asystent planowania”, a następnie wskaż projekty, które mają być sprawdzane "
            "pod kątem zajętych osób. Ustaw zakres dat, dni tygodnia, dostępne osoby "
            "oraz zasady. Planora przygotuje propozycję zbiórek bez dwóch kolejnych przydziałów tej samej osoby "
            "i z możliwie równym podziałem obowiązków.",
        ),
        (
            "Automatyczne terminy",
            "Zaznacz dowolną kombinację dni tygodnia, na przykład wszystkie środy, soboty i niedziele. "
            "Asystent wygeneruje odpowiadające im daty z wybranego zakresu.",
        ),
        (
            "Masowa edycja",
            "Otwórz projekt, uruchom Asystenta planowania i przejdź do zakładki „Masowa edycja”. "
            "Zaznacz konkretne terminy, aby wspólnie przesunąć ich daty albo ustawić godzinę i miejsce.",
        ),
        (
            "Kalendarz i przydziały osoby",
            "Zakładka „Kalendarz i przydziały” eksportuje cały projekt albo obowiązki wybranej osoby do ICS, "
            "który obsługują Google Calendar, Outlook i Kalendarz Apple. Przydziały jednej osoby można też zapisać do TXT.",
        ),
        (
            "Centrum projektów",
            "Przed otwarciem Centrum wybierasz zapisane projekty, które chcesz wspólnie sprawdzić. Centrum pokazuje centralny kalendarz, "
            "nadchodzące obowiązki, globalne kolizje, statystyki oraz indywidualny plan wybranej osoby. "
            "Możesz skopiować gotową wiadomość z przydziałami, otworzyć ją w programie pocztowym oraz drukować wiele planów naraz.",
        ),
        (
            "Cofanie i ponawianie",
            "Użyj Ctrl+Z, aby cofnąć zmianę, oraz Ctrl+Y lub Ctrl+Shift+Z, aby ją ponowić. Polecenia są też dostępne "
            "w menu „Edycja”. Planora grupuje szybko wpisywany tekst w czytelne kroki historii.",
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
            "gdy ta sama osoba ma kilka obowiązków tego samego dnia. Po wybraniu grupy Planora automatycznie "
            "ustawia jej grupowego jako osobę odpowiedzialną za sprzątanie, korzystając z ostatniego planu grup służby.",
        ),
        (
            "Plan zebrań w tygodniu",
            "Dodaj zebranie, sekcje i punkty programu. Możesz zmieniać kolory sekcji oraz dodać "
            "wydarzenie specjalne z tytułem, podtytułem i obrazem. W podglądzie i eksporcie "
            "punkty są automatycznie numerowane od pierwszego punktu po uwagach wstępnych. "
            "Górny pasek przełącza dni bez wracania do listy, a duplikowanie zebrania ustawia "
            "datę tydzień później. Możesz wstawić pełny lokalny szablon punktów albo pobrać program "
            "bieżącego lub wskazanego tygodnia z JW. Import od razu tworzy nowe zwykłe zebranie z datą środy "
            "wybranego tygodnia; importowane przydziały osób pozostają puste.",
        ),
        (
            "Plan grup służby",
            "Wpisz własny nagłówek, ustaw liczbę i kolejność grup, potem wybierz osoby z biblioteki. "
            "Nowa osoba jest członkiem grupy; grupowy i asystent są wyróżniani w eksporcie. Pierwszy utworzony plan "
            "grup pozostaje na stałe, a każda zmiana jest automatycznie zapisywana bez używania przycisku „Zapisz”.",
        ),
        (
            "Zbiórki do służby",
            "Edytuj tytuł, okres, nazwy kolumn, notatkę i kolory dokumentu. Następnie dodawaj terminy, "
            "godziny, miejsca oraz prowadzących. Każdą zbiórkę można duplikować i swobodnie przesuwać.",
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
            "Automatyczny zapis i odzyskiwanie",
            "Podczas edycji Planora tworzy lokalną kopię awaryjną co 20 sekund. Po nieprawidłowym zamknięciu "
            "zaproponuje odzyskanie ostatniego projektu. Kopie awaryjne są przechowywane osobno i nie trafiają "
            "do Asystenta ani Centrum projektów.",
        ),
        (
            "Wybór projektów do analizy",
            "Zapisane projekty trafiają domyślnie do osobnego katalogu „projects”. Przed otwarciem Asystenta lub Centrum "
            "wybierz konkretne pliki JSON albo świadomie dołącz aktualnie otwarty projekt. Dzięki temu stare i robocze wersje "
            "nie zniekształcają kolizji ani statystyk. Plan grup służby nadal ma osobny trwały zapis.",
        ),
        (
            "Kontrola przed eksportem",
            "Przed utworzeniem PDF lub JPG Planora sprawdza puste daty, brakujące osoby i podwójne przydziały. "
            "Możesz wrócić do edycji albo świadomie kontynuować eksport mimo ostrzeżeń.",
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
        tabs.addTab(self._jw_tab(), "Import z JW")
        tabs.addTab(self._cards_tab(self.PEOPLE, "Jedna lista nazwisk dla całej aplikacji."), "Lista osób")
        tabs.addTab(self._cards_tab(self.PLANNING, "Szybsze przygotowanie wielu terminów i przydziałów."), "Planowanie")
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
        subtitle = QLabel("Przejrzysty przewodnik po projektach, imporcie z JW, osobach, eksporcie i ustawieniach.")
        subtitle.setObjectName("screenSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        facts = QHBoxLayout()
        for text in ("5 generatorów", "Import z JW", "PDF, JPG i ICS", "Lokalne dane"):
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

    def _jw_tab(self) -> QScrollArea:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        intro = QLabel(
            "Pobierz program zebrania ze strony JW w kilka chwil. Planora korzysta z publicznej strony "
            "spotkań pod adresem wol.jw.org i nie zapisuje danych logowania."
        )
        intro.setObjectName("screenSubtitle")
        intro.setWordWrap(True)
        content_layout.addWidget(intro)

        open_page = QPushButton("Otwórz stronę spotkań JW")
        open_page.setObjectName("primaryButton")
        open_page.setToolTip(JW_MEETINGS_BASE_URL)
        open_page.clicked.connect(self.open_jw_meetings_page)
        content_layout.addWidget(open_page)

        address = QLabel(JW_MEETINGS_BASE_URL)
        address.setObjectName("helpText")
        address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        address.setWordWrap(True)
        content_layout.addWidget(address)

        for heading, text in self.JW_IMPORT:
            content_layout.addWidget(self._card(heading, text))
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def open_jw_meetings_page():
        QDesktopServices.openUrl(QUrl(JW_MEETINGS_BASE_URL))

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
