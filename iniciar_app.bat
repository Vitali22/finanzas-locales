@echo off
setlocal
cd /d "%~dp0"
title Finanzas Locales

echo.
echo ============================================
echo  Finanzas Locales
echo ============================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py"
  goto run_app
)

where python >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=python"
  goto run_app
)

echo No se encontro Python en esta computadora.
echo Instala Python 3 desde https://www.python.org/downloads/
echo Marca la opcion "Add python.exe to PATH" durante la instalacion.
pause
exit /b 1

:run_app
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno local...
  %PY_CMD% -m venv .venv
  if errorlevel 1 pause & exit /b 1
)

echo Instalando o actualizando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 pause & exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1

echo.
echo Abriendo la app en http://localhost:5000
echo Deja esta ventana abierta mientras uses la app.
start "" "http://localhost:5000"
".venv\Scripts\python.exe" app.py
pause
