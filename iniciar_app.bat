@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install -r requirements.txt
  if errorlevel 1 pause & exit /b 1
  py app.py
  pause
  exit /b 0
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -m pip install -r requirements.txt
  if errorlevel 1 pause & exit /b 1
  python app.py
  pause
  exit /b 0
)

echo No se encontro Python en esta computadora.
echo Instala Python 3 desde https://www.python.org/downloads/
echo Marca la opcion "Add python.exe to PATH" durante la instalacion.
pause
