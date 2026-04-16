@echo off
setlocal

REM Run from this folder even if launched elsewhere
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Could not find project virtual environment Python.
  echo Expected one of:
  echo   %~dp0..\.venv\Scripts\python.exe
  echo   %~dp0.venv\Scripts\python.exe
  pause
  exit /b 1
)

REM Quick dependency check (installs if missing)
"%PYTHON_EXE%" -c "import streamlit, pandas, psycopg, dotenv" >nul 2>&1
if errorlevel 1 (
  echo Installing required packages...
  "%PYTHON_EXE%" -m pip install -r requirements.txt
)

echo Starting Inventory System...
echo (App will auto-stop shortly after you close the tab)
"%PYTHON_EXE%" run_local.py
