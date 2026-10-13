# CanyonGlow v1.0 - Developer notes

This guide belongs to the source project and is not included in the installer or portable ZIP.

## Running from source

Only this method requires **Python 3.10 or newer with Tkinter** and `pyserial`.
Run these commands in the source project:

```bat
python -m pip install -r requirements.txt
python canyonglow.py
```

---

## Build as EXE (Windows)

The build machine needs **64-bit Python with Tkinter**, the packages listed in
`requirements-build.txt`, and **Inno Setup 6.3 or newer**:

```bat
py -3 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
build_windows.bat
```

Creates a PyInstaller folder bundle **without UPX**, checks the bundled GUI in a
hidden test covering profile loading, language switching and the internal dry-run
without accessing the controller, and then builds a German/English
Inno Setup installer. The target machine does not need Python installed.

Outputs for v1.0:

- `dist\CanyonGlow\CanyonGlow.exe` — keep the entire folder together.
- `dist\CanyonGlow-v1.0-Portable-x64.zip` — extract and launch the EXE inside the folder.
- `dist\CanyonGlow-v1.0-Setup-x64.exe` — per-user installation with a Start Menu shortcut,
  an optional desktop shortcut, and an uninstaller.
- `dist\CanyonGlow-v1.0-SHA256SUMS.txt` — checksums of the generated files.

The installer version is read automatically from `APP_VERSION`. A new setup
updates the existing installation. The installation folder and existing
profiles are retained.
The installer does not remove additional profile files; Start Menu and desktop
shortcuts use the Documents folder as their working directory.
The serial device driver is not installed by setup. Both the installer and ZIP
include `drivers\README_EN.txt` with brief instructions for Windows Update and
the official Prolific download.
In the source project, the EXE, window, setup and shortcut icon is stored in `picture\CanyonGlow.ico`.
The original geometric icon uses CanyonGlow's MIT license. Editable artwork is
in `picture\CanyonGlow.svg`, with a preview in `picture\CanyonGlow.png`.
Optional regeneration: `python -m pip install pillow`, then `python make_icon.py`.
The normal build uses the existing ICO and does not require Pillow.

To build only the folder and portable ZIP: `build_windows.bat --bundle-only`.
For custom tool locations, set `NUC_BUILD_PYTHON` (Python executable) and
`NUC_INNO_ISCC` (Inno Setup compiler `ISCC.exe`). An existing `.venv-build` is
preferred. The current spec file is generated at
`build\windows-release\spec\CanyonGlow.spec`. Outputs are initially unsigned.

---

