@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.9+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

pip install -r requirements.txt -q --disable-pip-version-check >nul 2>&1
if %errorlevel% neq 0 (
    pip install -r requirements.txt --no-cache-dir
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

python app.py
pause
