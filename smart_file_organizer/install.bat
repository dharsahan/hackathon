@echo off
:: ============================================================================
:: Smart File Organizer - Windows Installation Script
:: ============================================================================
:: This script installs all dependencies and sets up auto-start via Task Scheduler
:: Requires: Windows 10/11, Python 3.9+
:: ============================================================================

setlocal enabledelayedexpansion

:: Colors (Windows 10+)
set "GREEN=[32m"
set "YELLOW=[33m"
set "BLUE=[34m"
set "RED=[31m"
set "NC=[0m"

:: Get script directory
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\venv"
set "TASK_NAME=SmartFileOrganizer"

echo.
echo %BLUE%============================================================%NC%
echo %BLUE%     Smart File Organizer - Windows Installation Script     %NC%
echo %BLUE%============================================================%NC%
echo.

:: Check for admin rights (optional, for Task Scheduler)
net session >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[OK]%NC% Running with administrator privileges
) else (
    echo %YELLOW%[!]%NC% Running without admin rights - auto-start may require manual setup
)

echo.
echo This script will:
echo   1. Check Python installation
echo   2. Create Python virtual environment
echo   3. Install Python packages
echo   4. Create startup directories
echo   5. Setup auto-start ^(Task Scheduler^)
echo   6. Start the organizer
echo.

set /p "CONTINUE=Continue with installation? [Y/n]: "
if /i "%CONTINUE%"=="n" (
    echo Installation cancelled.
    exit /b 0
)

:: ============================================================================
:: Step 1: Check Python
:: ============================================================================
echo.
echo %BLUE%Checking Python installation...%NC%

where python >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[X]%NC% Python not found!
    echo.
    echo Please install Python 3.9+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo %GREEN%[OK]%NC% Python %PYTHON_VERSION% found

:: Check Python version is 3.9+
python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if %errorLevel% neq 0 (
    echo %RED%[X]%NC% Python 3.9+ required, found %PYTHON_VERSION%
    pause
    exit /b 1
)

:: ============================================================================
:: Step 2: Create Virtual Environment
:: ============================================================================
echo.
echo %BLUE%Setting up Python virtual environment...%NC%

if exist "%VENV_DIR%" (
    echo %YELLOW%[!]%NC% Virtual environment already exists, skipping creation
) else (
    python -m venv "%VENV_DIR%"
    if %errorLevel% neq 0 (
        echo %RED%[X]%NC% Failed to create virtual environment
        pause
        exit /b 1
    )
    echo %GREEN%[OK]%NC% Virtual environment created
)

:: Upgrade pip
echo %BLUE%Upgrading pip...%NC%
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip -q
echo %GREEN%[OK]%NC% Pip upgraded

:: ============================================================================
:: Step 3: Install Dependencies
:: ============================================================================
echo.
echo %BLUE%Installing Python dependencies...%NC%

"%VENV_DIR%\Scripts\pip.exe" install -r "%SCRIPT_DIR%\requirements.txt" -q
if %errorLevel% neq 0 (
    echo %RED%[X]%NC% Failed to install dependencies
    pause
    exit /b 1
)
echo %GREEN%[OK]%NC% Python dependencies installed

:: ============================================================================
:: Step 4: Create Directories
:: ============================================================================
echo.
echo %BLUE%Creating directories...%NC%

if not exist "%USERPROFILE%\Downloads" mkdir "%USERPROFILE%\Downloads"
if not exist "%USERPROFILE%\Desktop" mkdir "%USERPROFILE%\Desktop"
if not exist "%USERPROFILE%\Organized" mkdir "%USERPROFILE%\Organized"
if not exist "%USERPROFILE%\Organized\.quarantine" mkdir "%USERPROFILE%\Organized\.quarantine"
if not exist "%USERPROFILE%\Organized\Vault" mkdir "%USERPROFILE%\Organized\Vault"

echo %GREEN%[OK]%NC% Directories created

:: ============================================================================
:: Step 5: Create Windows config.yaml
:: ============================================================================
echo.
echo %BLUE%Creating Windows configuration...%NC%

:: Create Windows-compatible config if doesn't exist
if not exist "%SCRIPT_DIR%\config.yaml" (
    (
        echo watcher:
        echo   watch_directories:
        echo     - "%USERPROFILE:\=/%/Downloads"
        echo     - "%USERPROFILE:\=/%/Desktop"
        echo   ignore_patterns:
        echo     - "*.tmp"
        echo     - "*.crdownload"
        echo     - "~$*"
        echo     - "Thumbs.db"
        echo     - "desktop.ini"
        echo     - "*.part"
        echo   debounce_seconds: 1.0
        echo   recursive: false
        echo.
        echo organization:
        echo   base_directory: "%USERPROFILE:\=/%/Organized"
        echo   quarantine_directory: "%USERPROFILE:\=/%/Organized/.quarantine"
        echo   vault_directory: "%USERPROFILE:\=/%/Organized/Vault"
        echo   use_date_folders: true
        echo   date_format: '%%Y/%%m'
        echo   organize_in_place: false
        echo.
        echo classification:
        echo   llm_backend: ollama
        echo   llm_model: gemma3:270m
        echo   max_text_length: 2000
        echo   ocr_enabled: false
        echo   zero_shot_model: facebook/bart-large-mnli
        echo   fallback_to_zero_shot: true
        echo.
        echo deduplication:
        echo   enabled: true
        echo   use_partial_hash: true
        echo   partial_hash_size: 4096
        echo   perceptual_hash_threshold: 5
        echo   duplicate_action: quarantine
        echo.
        echo security:
        echo   enable_encryption: true
        echo   encryption_algorithm: AES-256-GCM
        echo   key_derivation: argon2id
        echo   secure_delete_passes: 3
    ) > "%SCRIPT_DIR%\config.yaml"
    echo %GREEN%[OK]%NC% Configuration created
) else (
    echo %YELLOW%[!]%NC% Configuration already exists, keeping current settings
)

:: ============================================================================
:: Step 6: Create Start Script
:: ============================================================================
echo.
echo %BLUE%Creating start script...%NC%

(
    echo @echo off
    echo cd /d "%SCRIPT_DIR%"
    echo "%VENV_DIR%\Scripts\python.exe" -m src.main
) > "%SCRIPT_DIR%\start.bat"

echo %GREEN%[OK]%NC% Start script created

:: ============================================================================
:: Step 7: Setup Task Scheduler (Auto-Start)
:: ============================================================================
echo.
echo %BLUE%Setting up auto-start...%NC%

:: Delete existing task if present
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create new scheduled task
schtasks /create /tn "%TASK_NAME%" /tr "\"%SCRIPT_DIR%\start.bat\"" /sc onlogon /rl highest /f >nul 2>&1
if %errorLevel% == 0 (
    echo %GREEN%[OK]%NC% Auto-start configured ^(Task Scheduler^)
) else (
    echo %YELLOW%[!]%NC% Could not setup auto-start - you can run start.bat manually
)

:: ============================================================================
:: Step 8: Start the Service
:: ============================================================================
echo.
echo %BLUE%Starting Smart File Organizer...%NC%

:: Start in background
start "" /min "%SCRIPT_DIR%\start.bat"
timeout /t 3 /nobreak >nul

echo %GREEN%[OK]%NC% Smart File Organizer started

:: ============================================================================
:: Done!
:: ============================================================================
echo.
echo %GREEN%============================================================%NC%
echo %GREEN%             Installation Complete!                         %NC%
echo %GREEN%============================================================%NC%
echo.
echo The Smart File Organizer is now running in the background.
echo It will automatically start when you log in.
echo.
echo %BLUE%Watching:%NC%
echo   - %USERPROFILE%\Downloads
echo   - %USERPROFILE%\Desktop
echo.
echo %BLUE%Dashboard:%NC% http://127.0.0.1:3000
echo.
echo %BLUE%Commands:%NC%
echo   Start:  %SCRIPT_DIR%\start.bat
echo   Stop:   Close the command window or use Task Manager
echo   Config: %SCRIPT_DIR%\config.yaml
echo.
echo %BLUE%Task Scheduler:%NC%
echo   Open "Task Scheduler" and find "%TASK_NAME%" to manage auto-start
echo.

pause
