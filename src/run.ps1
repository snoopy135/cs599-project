# AI Recruitment Policy Q&A Assistant - PowerShell Launcher
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Check & install dependencies
python --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python not found. Install Python 3.9+ from https://www.python.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
pip install -r requirements.txt -q --disable-pip-version-check 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    pip install -r requirements.txt --no-cache-dir
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to install deps" -ForegroundColor Red; exit 1 }
}

# Start (app.py handles browser opening)
python app.py
