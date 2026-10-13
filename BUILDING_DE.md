# CanyonGlow v1.0 - Entwicklerhinweise

Diese Anleitung gehört zum Quellprojekt und wird nicht mit Setup oder Portable-ZIP ausgeliefert.

## Aus dem Quellcode starten

Nur hierfür werden **Python 3.10 oder neuer mit Tkinter** und `pyserial` benötigt.
Im Quellprojekt ausführen:

```bat
python -m pip install -r requirements.txt
python canyonglow.py
```

---

## Als EXE bauen (Windows)

Auf dem Build-Rechner werden **64-Bit-Python mit Tkinter**, die Pakete aus
`requirements-build.txt` und **Inno Setup 6.3 oder neuer** benötigt:

```bat
py -3 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
build_windows.bat
```

Erstellt einen PyInstaller-Ordnerbuild **ohne UPX**, prüft die gebündelte
Oberfläche einschließlich Profil-Laden, Sprachwechsel und internem Dry-Run in
einem versteckten Test ohne Controllerzugriff und baut anschließend
einen deutsch/englischen Inno-Setup-Installer. Auf dem Zielrechner ist kein Python
erforderlich.

Ausgaben für v1.0:

- `dist\CanyonGlow\CanyonGlow.exe` — der gesamte Ordner wird zum Start benötigt.
- `dist\CanyonGlow-v1.0-Portable-x64.zip` — entpacken und die EXE im Ordner starten.
- `dist\CanyonGlow-v1.0-Setup-x64.exe` — Installation im Benutzerkonto mit Startmenü-Eintrag,
  optionaler Desktop-Verknüpfung und Deinstallation.
- `dist\CanyonGlow-v1.0-SHA256SUMS.txt` — Prüfsummen der erzeugten Dateien.

Die Setup-Version wird automatisch aus `APP_VERSION` gelesen. Ein neues Setup
aktualisiert die bestehende Installation. Der Installationsordner und vorhandene
Profile bleiben erhalten.
Der Installer löscht keine zusätzlich angelegten Profil-Dateien; Startmenü- und
Desktop-Verknüpfungen verwenden den Dokumente-Ordner als Arbeitsverzeichnis.
Der serielle Gerätetreiber wird nicht mitinstalliert. Die kurze Anleitung
`drivers\README_DE.txt` liegt sowohl dem Setup als auch dem ZIP bei und enthält
Hinweise zu Windows Update sowie den offiziellen Prolific-Download.
Im Quellprojekt liegt das Symbol für EXE, Fenster, Setup und Verknüpfungen in `picture\CanyonGlow.ico`.
Das eigene geometrische Icon steht wie CanyonGlow unter MIT; die bearbeitbare
Grafik liegt in `picture\CanyonGlow.svg`, die Vorschau in `picture\CanyonGlow.png`.
Optional neu erzeugen: `python -m pip install pillow` und `python make_icon.py`.
Der normale Build verwendet die vorhandene ICO-Datei und benötigt kein Pillow.

Nur den Ordnerbuild und das portable ZIP erstellen: `build_windows.bat --bundle-only`.
Bei abweichenden Werkzeugpfaden können `NUC_BUILD_PYTHON` (Python-EXE) und
`NUC_INNO_ISCC` (Inno-Setup-Compiler `ISCC.exe`) gesetzt werden.
Eine vorhandene `.venv-build` wird bevorzugt verwendet. Die aktuelle Spec-Datei
wird unter `build\windows-release\spec\CanyonGlow.spec` erzeugt.
Die Ausgaben sind zunächst unsigniert.

---

