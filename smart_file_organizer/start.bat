@echo off
:: Smart File Organizer - Quick Start Script
:: Use this to run the organizer (uses the virtual environment)

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo.
    echo ERROR: Virtual environment not found!
    echo.
    echo Please run install.bat first to set up the application.
    echo.
    pause
    exit /b 1
)

echo Starting Smart File Organizer...
echo Dashboard: http://127.0.0.1:3000
echo.
echo Press Ctrl+C to stop.
echo.

venv\Scripts\python.exe -m src.main
