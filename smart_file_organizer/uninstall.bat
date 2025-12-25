@echo off
:: Smart File Organizer - Windows Uninstall Script
:: Removes the scheduled task and optionally the virtual environment

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\venv"
set "TASK_NAME=SmartFileOrganizer"

echo.
echo ============================================================
echo      Smart File Organizer - Uninstall Script
echo ============================================================
echo.

:: Stop any running instance
echo Stopping Smart File Organizer...
taskkill /f /im python.exe /fi "WINDOWTITLE eq Smart File*" >nul 2>&1
echo [OK] Stopped running instances

:: Remove scheduled task
echo Removing auto-start task...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Auto-start task removed
) else (
    echo [!] No auto-start task found
)

:: Ask about virtual environment
echo.
set /p "REMOVE_VENV=Remove virtual environment? This will require reinstallation. [y/N]: "
if /i "%REMOVE_VENV%"=="y" (
    if exist "%VENV_DIR%" (
        rmdir /s /q "%VENV_DIR%"
        echo [OK] Virtual environment removed
    ) else (
        echo [!] Virtual environment not found
    )
) else (
    echo [OK] Virtual environment kept
)

:: Remove start script
if exist "%SCRIPT_DIR%\start.bat" (
    del "%SCRIPT_DIR%\start.bat"
    echo [OK] Start script removed
)

echo.
echo ============================================================
echo                   Uninstall Complete!
echo ============================================================
echo.
echo The Smart File Organizer has been removed from auto-start.
echo Your organized files in %USERPROFILE%\Organized have NOT been removed.
echo.
echo To completely remove, delete the folder:
echo   %SCRIPT_DIR%
echo.

pause
