#!/bin/bash
# Fiji Automated Analysis - Unix Shell Script
# Usage: ./run_analysis.sh [path_to_images] [options]

echo "Fiji Automated Analysis Tool"
echo "=========================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "Error: Python is not installed or not in PATH"
        echo "Please install Python 3.7 or higher"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.7"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "Error: main.py not found"
    echo "Please run this script from the Fiji Automated Analysis directory"
    exit 1
fi

# If no arguments provided, show help
if [ $# -eq 0 ]; then
    echo ""
    echo "Usage: $0 [path_to_documents] [options]"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/documents --keyword 4MU"
    echo "  $0 /path/to/documents --keyword 4MU --keyword Control --apply-roi"
    echo "  $0 /path/to/documents --keyword Control --commands \"open_standard measure quit\""
    echo "  $0 /path/to/documents --validate"
    echo ""
    exit 0
fi

# Run the analysis
echo "Running analysis..."
$PYTHON_CMD main.py "$@"

# Check if the command was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "Analysis completed successfully"
else
    echo ""
    echo "Analysis completed with errors"
    exit 1
fi
