@echo off
setlocal
REM Fiji Automated Analysis - Windows Batch Script
REM Usage: run_analysis.bat [path_to_images] [options]

echo Fiji Automated Analysis Tool
echo ==========================

set "APP_DIR=%~dp0.."
cd /d "%APP_DIR%"

REM Check if Python is available
set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist "%APP_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%APP_DIR%\.venv\Scripts\python.exe"
    goto python_found
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    goto python_found
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=python"
    goto python_found
)

echo Error: Python is not installed or not in PATH
echo Please install Python 3.10 or higher
pause
exit /b 1

:python_found
"%PYTHON_EXE%" %PYTHON_ARGS% -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
if %ERRORLEVEL% neq 0 (
    echo Error: Python 3.10 or higher is required
    pause
    exit /b 1
)

REM Check if package exists
if not exist "%APP_DIR%\fiji_automated_analysis\cli.py" (
    echo Error: package CLI module not found
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
    echo   run_analysis.bat C:\Data --keyword Exp
    echo   run_analysis.bat C:\Data --keyword Exp --keyword Control --apply-roi
    echo   run_analysis.bat C:\Data --keyword Control --macro-file analysis.ijm
    echo   run_analysis.bat --list-macros
    echo.
    pause
    exit /b 0
)

REM Run the analysis
echo Running analysis...
"%PYTHON_EXE%" %PYTHON_ARGS% -m fiji_automated_analysis.cli %*

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
