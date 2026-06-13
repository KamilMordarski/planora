# Podpisywanie Planory dla Windows

Microsoft Defender SmartScreen ocenia reputację pobranego pliku oraz podpisu
wydawcy. Metadane EXE i sumy SHA-256 pomagają zweryfikować plik, ale nie
zastępują podpisu Authenticode wystawionego przez zaufany urząd certyfikacji.

## Co jest już przygotowane

- build Windows zawiera nazwę produktu, autora, opis i numer wersji,
- każde wydanie publikuje `SHA256SUMS.txt`,
- GitHub Actions podpisuje EXE przed pakowaniem, gdy skonfigurowane są sekrety,
- workflow sprawdza poprawność podpisu przed opublikowaniem plików.

## Podłączenie certyfikatu PFX

1. Uzyskaj certyfikat przeznaczony do podpisywania kodu.
2. Wyeksportuj go wraz z kluczem prywatnym do chronionego hasłem pliku PFX.
3. Zakoduj plik do Base64:

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("planora-code-signing.pfx")) |
     Set-Clipboard
   ```

4. W ustawieniach repozytorium GitHub dodaj sekrety Actions:
   - `WINDOWS_CERTIFICATE_BASE64` - zawartość Base64 pliku PFX,
   - `WINDOWS_CERTIFICATE_PASSWORD` - hasło pliku PFX.
5. Opublikuj nowy tag wersji. Workflow podpisze plik `Planora.exe`, sprawdzi
   podpis, a następnie utworzy ZIP i bezpośrednie pliki EXE.

Nie dodawaj pliku PFX ani jego hasła do repozytorium.

## Inne możliwości

Nowoczesne certyfikaty OV często przechowują klucz w tokenie sprzętowym lub
usłudze HSM. W takim przypadku należy zastąpić krok PFX integracją dostawcy.
Microsoft Store podpisuje pakiety MSIX po certyfikacji i jest alternatywą dla
samodzielnego rozpowszechniania plików EXE.
