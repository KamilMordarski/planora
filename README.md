# Planora

Planora to modularna aplikacja desktopowa w Pythonie i PySide6 do tworzenia,
zapisywania oraz eksportowania grafików do PDF i JPG.

> Planora jest niezależnym, nieoficjalnym narzędziem. Nie jest oficjalną
> aplikacją Świadków Jehowy ani żadnej powiązanej organizacji.

## Pobieranie

Gotowy plik EXE dla Windows i paczka dla macOS są dostępne w
[`downloads/latest`](downloads/latest/). Starsze wersje znajdują się w
[`downloads`](downloads/).

Każde wydanie Windows zawiera sumy SHA-256. Konfiguracja podpisu Authenticode
jest opisana w [`CODE_SIGNING.md`](CODE_SIGNING.md).

Obecnie dostępne szablony:

- **Wykład publiczny i Studium Strażnicy**
- **Sprzątanie sali, nagłośnienie i porządkowi** z wykrywaniem kolizji obowiązków
- **Plan zebrań w tygodniu** z edytowalnymi sekcjami programu i wydarzeniami specjalnymi
- **Plan grup służby** z dowolną liczbą grup i rolami członków
- **Zbiórki do służby** z edytowalnymi kolumnami, kolorami, terminami i prowadzącymi

Szablon sprzątania i porządkowych porównuje zakresy tygodniowe z konkretnymi
datami zebrań. Ostrzega, gdy ta sama osoba ma danego dnia więcej niż jeden
obowiązek, na przykład konsolę Zoom oraz służbę porządkowego.

Szablon zebrań w tygodniu umożliwia dodawanie własnych sekcji i punktów,
przypisywanie uczestników z biblioteki osób oraz umieszczanie wydarzeń
specjalnych z tytułem, podtytułem i obrazem. Właściwe punkty programu są
automatycznie numerowane od pierwszego punktu po uwagach wstępnych. Pasek
szybkiego wyboru pozwala zmieniać edytowane zebranie z każdego kroku, a całe
zebranie lub pojedynczy punkt można duplikować, aby ograniczyć powtarzalne wpisywanie.

Plan grup służby pozwala swobodnie dodawać, usuwać i porządkować grupy oraz
ich członków. Grupowy i asystent są czytelnie, ale subtelnie wyróżnieni
w eksporcie, a każda nowa osoba domyślnie otrzymuje rolę członka grupy.
Nowy projekt nie zawiera domyślnej nazwy zboru. Zakładka osób dopasowuje się
do szerokości okna i przeznacza większość miejsca na czytelną edycję nazwisk.

## Personalizacja interfejsu

W ustawieniach aplikacji można wybrać jeden z pięciu motywów, ustawić własny
kolor akcentu, zmienić skalę i gęstość interfejsu, kształt kontrolek, szybkość
animacji oraz zachowanie dźwięków i logo startowego. Przyciski, nawigacja,
dodawanie, usuwanie, zapis i eksport mają własne subtelne efekty. Ustawienia
interfejsu nie wpływają na wygląd eksportowanych plików.

Poradnik dostępny z menu głównego opisuje cały proces tworzenia grafiku,
import biblioteki osób, pliki projektów, eksport, ustawienia i aktualizacje.

Każdy edytor prowadzi przez kolejne, swobodnie przełączane kroki. Ostatni krok
zawiera duży podgląd dokumentu z dopasowaniem strony oraz kontrolą powiększenia.
Kafelki, formularze i układ ekranów dopasowują się do szerokości okna.
Nowe projekty nie zawierają przykładowych dat, osób ani przydziałów.

Terminy można tworzyć bez dodawania pustego wpisu. Wystarczy uzupełnić formularz
i wybrać **Dodaj z formularza**. Przycisk **Nowy formularz** pozwala przygotować
kolejny termin bez przypadkowego zmieniania wcześniej wybranego wpisu.

## Asystent planowania i role

Biblioteka osób przechowuje role i uprawnienia, między innymi prowadzenie zbiórek,
obsługę konsoli, mikrofonów, służbę porządkową i udział w programie. Generatory
podpowiadają kandydatów pasujących do danego zadania, a pola pozostają edytowalne
w razie wyjątkowego przydziału.

Nowa instalacja Planory zawsze rozpoczyna pracę z całkowicie pustą biblioteką
osób. Aplikacja nie zawiera przykładowych ani domyślnych nazwisk.

Bibliotekę osób można wyeksportować do jednego pliku JSON zawierającego nazwiska
i przypisane uprawnienia. Ponowny import takiego pliku odtwarza role i pomija
duplikaty. Starsze pliki będące prostą listą nazwisk nadal są obsługiwane.

Centralny Asystent planowania generuje wybrane dni tygodnia z zakresu dat,
tworzy propozycję zbiórek z równym podziałem obowiązków i unika tej samej osoby
dwa razy z rzędu. Uwzględnia obowiązki z ostatnio edytowanych projektów i nie
tworzy przydziału osobie zajętej tego samego dnia. Pozwala też zaznaczyć kilka terminów do wspólnej zmiany,
wyeksportować kalendarz ICS dla Google Calendar, Outlooka i Kalendarza Apple
oraz zapisać listę przydziałów konkretnej osoby.

Podczas edycji aktywny projekt jest automatycznie zapisywany co 20 sekund.
Po nieprawidłowym zamknięciu Planora proponuje odzyskanie kopii awaryjnej.

Centrum projektów korzysta z osobnego lokalnego archiwum, które jest aktualizowane
automatycznie podczas pracy. Łączy przydziały w centralnym kalendarzu, wykrywa
kolizje między projektami, pokazuje statystyki równego podziału i tworzy
indywidualny plan osoby. Wpisy archiwum starsze niż 90 dni są automatycznie
usuwane. Przed każdym eksportem Planora pokazuje panel kontroli brakujących
danych i kolizji. Zmiany można cofać i ponawiać przez menu **Edycja** oraz
skróty `Ctrl+Z` i `Ctrl+Y`.

## Uruchomienie

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

## Testy

```bash
python -m unittest discover
```

## Dodawanie kolejnego typu grafiku

1. Utwórz katalog w `app/templates/`.
2. Dodaj klasę szablonu udostępniającą metadane, edytor, renderer i domyślny projekt.
3. Zarejestruj jedną instancję klasy w `app/core/template_registry.py`.

Okno główne i ekran wyboru automatycznie pokażą nowy typ.

## Dane użytkownika

Biblioteka osób i ustawienia są przechowywane w katalogu danych użytkownika:

- Windows: `%APPDATA%\Planora`
- macOS: `~/Library/Application Support/Planora`
- Linux: `~/.local/share/planora`

Automatyczne archiwum projektów znajduje się w podkatalogu `project-archive`.
Nie zastępuje ono własnych plików JSON i jest utrzymywane wyłącznie przez 90 dni.

Przy pierwszym uruchomieniu istniejąca biblioteka `data/people.json` zostanie
skopiowana do katalogu użytkownika. Dane ze starszego katalogu
`GeneratorGrafikow` są automatycznie przenoszone do Planory.

Bibliotekę można uzupełnić przez import pliku JSON zawierającego tablicę nazwisk
albo obiekt z polem `people`. Import łączy listy i pomija duplikaty. Eksport
biblioteki zapisuje osoby wraz z rolami w jednym przenośnym pliku JSON.

## Aktualizacje

Aplikacja korzysta ze stałego adresu
`https://raw.githubusercontent.com/KamilMordarski/planora/main/update.json`.
Nie należy go zmieniać. Planora wyłącznie sprawdza wersję i, po potwierdzeniu
użytkownika, pobiera bezpośrednio właściwy plik ZIP dla Windows lub macOS.
Gotowa aplikacja następnie zamyka się, instaluje aktualizację i uruchamia ponownie.
Jeśli podmiana plików się nie powiedzie, instalator przywraca poprzednią wersję.
Restart po aktualizacji jest uruchamiany jako niezależny proces, dzięki czemu
nowa wersja nie dziedziczy tymczasowego środowiska poprzedniej aplikacji.

Gotowa instrukcja konfiguracji aktualizacji przez GitHub znajduje się w
[`UPDATE_SETUP.md`](UPDATE_SETUP.md). Plik można przygotować poleceniem:

```bash
python tools/prepare_update.py --repo KamilMordarski/planora --note "Opis wydania"
```

## Budowanie aplikacji

Separator w `--add-data` to `;` na Windows i `:` na macOS:

```bash
pip install pyinstaller

# Windows
pyinstaller --onefile --windowed --name Planora --icon app/assets/icons/app_icon.png --add-data "app/assets;app/assets" main.py

# macOS
pyinstaller --onefile --windowed --name Planora --add-data "app/assets:app/assets" main.py
```
