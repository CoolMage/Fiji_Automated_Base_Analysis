#!/bin/bash
# Fiji Automated Analysis - Unix Shell Script
# Usage: ./run_analysis.sh [path_to_images] [options]

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

echo "Fiji Automated Analysis Tool"
echo "=========================="

# Check if Python is available
if [ -x "$APP_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$APP_DIR/.venv/bin/python"
elif ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "Error: Python is not installed or not in PATH"
        echo "Please install Python 3.10 or higher"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
if ! "$PYTHON_CMD" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Error: Python 3.10 or higher is required"
    echo "Current version: $($PYTHON_CMD --version 2>&1)"
    exit 1
fi

# Check if package exists
if [ ! -f "$APP_DIR/fiji_automated_analysis/cli.py" ]; then
    echo "Error: package CLI module not found"
    echo "Please run this script from the Fiji Automated Analysis directory"
    exit 1
fi

# If no arguments provided, show help
if [ $# -eq 0 ]; then
    echo ""
    echo "Usage: $0 [path_to_documents] [options]"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/documents --keyword Exp"
    echo "  $0 /path/to/documents --keyword Exp --keyword Control --apply-roi"
    echo "  $0 /path/to/documents --keyword Control --macro-file analysis.ijm"
    echo "  $0 --list-macros"
    echo "  $0 /path/to/documents --validate"
    echo ""
    exit 0
fi

# Run the analysis
echo "Running analysis..."
set +e
$PYTHON_CMD -m fiji_automated_analysis.cli "$@"
STATUS=$?
set -e

# Check if the command was successful
if [ $STATUS -eq 0 ]; then
    echo ""
    echo "Analysis completed successfully"
else
    echo ""
    echo "Analysis completed with errors"
    exit 1
fi
