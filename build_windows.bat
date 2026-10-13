@echo off
setlocal
pushd "%~dp0"

if defined NUC_BUILD_PYTHON goto explicit_python
if exist ".venv-build\Scripts\python.exe" (
    set "NUC_BUILD_PYTHON=%CD%\.venv-build\Scripts\python.exe"
    goto explicit_python
)
py -3 -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
    py -3 -B build_windows.py %*
    goto finished
)
for /d %%P in ("%USERPROFILE%\AppData\Local\Programs\Python\Python3*") do (
    if exist "%%~fP\python.exe" set "NUC_BUILD_PYTHON=%%~fP\python.exe"
)
if defined NUC_BUILD_PYTHON goto explicit_python
python -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
    python -B build_windows.py %*
    goto finished
)
echo Python mit Tkinter fehlt. Bitte Python von python.org installieren.
echo Alternativ NUC_BUILD_PYTHON auf den vollstaendigen Python-Pfad setzen.
set "NUC_BUILD_RESULT=1"
goto exit_build

:explicit_python
"%NUC_BUILD_PYTHON%" -B build_windows.py %*

:finished
set "NUC_BUILD_RESULT=%ERRORLEVEL%"

:exit_build
popd
if not defined NUC_BUILD_NO_PAUSE pause
exit /b %NUC_BUILD_RESULT%
