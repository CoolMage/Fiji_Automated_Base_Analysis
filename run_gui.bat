@echo off
setlocal enabledelayedexpansion

REM Fiji Automated Analysis GUI Launcher - Windows Batch Script

echo Fiji Automated Analysis GUI
set PYTHON_CMD=

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    set PYTHON_CMD=python
) else (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.7 or higher and try again.
    exit /b 1
)

if not exist gui.py (
    echo Error: gui.py not found. Please run this script from the project root.
    exit /b 1
)

echo Checking and installing dependencies...
%PYTHON_CMD% -m pip install --upgrade pip >nul
%PYTHON_CMD% -m pip install -r requirements.txt

if not %ERRORLEVEL%==0 (
    echo Failed to install dependencies.
    exit /b 1
)

echo Starting GUI...
%PYTHON_CMD% gui.py %*
