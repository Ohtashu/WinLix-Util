@echo off
:: ─────────────────────────────────────────────────────────
::  Linux Toolkit — one-command launcher (Windows)
::  Usage:  run.bat
:: ─────────────────────────────────────────────────────────
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"

:: ── Ensure python is available ──────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: ── Create venv if missing or broken ─────────────────────
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

:: ── Install the toolkit if not already ───────────────────
"%VENV_DIR%\Scripts\python.exe" -c "import toolkit" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    "%VENV_DIR%\Scripts\pip.exe" install --upgrade pip -q
    "%VENV_DIR%\Scripts\pip.exe" install -e "%SCRIPT_DIR%" -q
)

:: ── Launch ───────────────────────────────────────────────
"%VENV_DIR%\Scripts\python.exe" -m toolkit %*
