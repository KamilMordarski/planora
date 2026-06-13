# Aktualizacje Planory przez GitHub

Planora nie podmienia swoich plików automatycznie. Pobiera mały plik `update.json`,
porównuje numery wersji i po zgodzie użytkownika otwiera stronę najnowszego wydania.

## Pierwsza konfiguracja

1. Utwórz publiczne repozytorium GitHub, na przykład `kamil/planora`.
2. Umieść w nim kod aplikacji razem z plikiem `update.json`.
3. W katalogu projektu uruchom:

```powershell
.venv\Scripts\python.exe tools\prepare_update.py --repo KamilMordarski/planora --note "Pierwsze wydanie Planory"
```

4. Zapisz i wyślij wygenerowany `update.json` do gałęzi `main`.
5. Planora korzysta ze stałego adresu:

```text
https://raw.githubusercontent.com/KamilMordarski/planora/main/update.json
```

6. Nie zmieniaj ścieżki ani nazwy pliku `update.json`, ponieważ aplikacja oczekuje
   go dokładnie pod tym adresem.

## Publikowanie kolejnej wersji

1. Zmień `APP_VERSION` i `LAST_UPDATE` w `app/core/app_info.py`.
2. Przygotuj nowy plik aktualizacji:

```powershell
.venv\Scripts\python.exe tools\prepare_update.py `
  --repo KamilMordarski/planora `
  --version 1.6.0 `
  --note "Opis pierwszej zmiany" `
  --note "Opis drugiej zmiany"
```

3. Wyślij zmiany do GitHub.
4. Utwórz i wyślij tag wersji:

```powershell
git tag v1.6.0
git push origin v1.6.0
```

Workflow `.github/workflows/release.yml` zbuduje wydanie dla Windows i macOS oraz
doda pliki ZIP do GitHub Releases. Link z `update.json` prowadzi do najnowszego
wydania, więc użytkownik sam wybiera właściwy plik.

## Ważne

- Repozytorium z `update.json` musi być publiczne albo dostępne bez logowania.
- Numer w `update.json` musi być wyższy od `APP_VERSION` użytkownika.
- Przed opublikowaniem zawsze uruchom testy: `python -m unittest discover -v`.
- Nie umieszczaj w repozytorium biblioteki osób ani prywatnych projektów JSON.
