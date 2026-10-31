@echo off
title Telegram Batch Media Forwarder
cd /d "%~dp0"

echo ============================================================
echo       Telegram Batch Media Forwarder - Setup & Launch
echo ============================================================
echo.

:: 1. Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] First-time setup: Creating Python environment...
    
    where uv >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        uv venv .venv
        uv pip install -r requirements.txt
    ) else (
        py -3 -m venv .venv 2>nul || python -m venv .venv
        if not exist ".venv\Scripts\python.exe" (
            echo [ERROR] Python was not found! Please install Python from https://www.python.org/
            pause
            exit /b 1
        )
        .venv\Scripts\python -m pip install --upgrade pip
        .venv\Scripts\python -m pip install -r requirements.txt
    )
    echo [INFO] Setup completed!
    echo.
)

:: 2. Launch the tool
.venv\Scripts\python telegram_file_forwarder.py

echo.
echo Press any key to close this window...
pause >nul
