@echo off
REM Fiji Automated Analysis - Windows Batch Script
REM Usage: run_analysis.bat [path_to_images] [options]

echo Fiji Automated Analysis Tool
echo ==========================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist "main.py" (
    echo Error: main.py not found
    echo Please run this script from the Fiji Automated Analysis directory
    pause
    exit /b 1
)

REM If no arguments provided, show help
if "%~1"=="" (
    echo.
    echo Usage: run_analysis.bat [path_to_documents] [options]
    echo.
    echo Examples:
    echo   run_analysis.bat C:\Data --keyword 4MU
    echo   run_analysis.bat C:\Data --keyword 4MU --keyword Control --apply-roi
    echo   run_analysis.bat C:\Data --keyword Control --commands "open_standard measure quit"
    echo   run_analysis.bat --list-commands
    echo.
    pause
    exit /b 0
)

REM Run the analysis
echo Running analysis...
python main.py %*

REM Check if the command was successful
if errorlevel 1 (
    echo.
    echo Analysis completed with errors
) else (
    echo.
    echo Analysis completed successfully
)

echo.
pause
