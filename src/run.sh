#!/bin/bash
# Recruitment Policy Q&A Assistant - Linux/Mac Launcher

echo "========================================"
echo "  AI Recruitment Policy Q&A Assistant"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/3] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Please install Python 3.9+"
    exit 1
fi
python3 --version

echo ""
echo "[2/3] Installing dependencies..."
pip3 install -r requirements.txt -q --disable-pip-version-check
if [ $? -ne 0 ]; then
    echo "  Retrying..."
    pip3 install -r requirements.txt --no-cache-dir
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install dependencies."
        exit 1
    fi
fi
echo "  Dependencies OK"

echo ""
echo "[3/3] Starting server..."
echo ""
echo "  URL:    http://localhost:5000"
echo "  Admin:  http://localhost:5000/admin/login"
echo "  Account: admin / admin123"
echo ""
echo "  Press Ctrl+C to stop."
echo "========================================"
echo ""

# Auto-open browser
if command -v open &> /dev/null; then
    open "http://localhost:5000" &
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:5000" &
fi

python3 app.py
