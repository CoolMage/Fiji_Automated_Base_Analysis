#!/bin/bash
# Fiji Automated Analysis GUI Launcher - Unix Shell Script

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "Fiji Automated Analysis GUI"
echo "==========================="

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed or not in PATH"
    echo "Please install Python 3.7 or higher and try again."
    exit 1
fi

if [ ! -f "gui.py" ]; then
    echo "Error: gui.py not found. Please run this script from the project root."
    exit 1
fi

echo "Checking and installing dependencies..."
$PYTHON_CMD -m pip install --upgrade pip >/dev/null
$PYTHON_CMD -m pip install -r requirements.txt

echo "Starting GUI..."
exec $PYTHON_CMD gui.py "$@"
