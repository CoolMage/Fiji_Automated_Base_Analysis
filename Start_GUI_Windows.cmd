@echo off
setlocal

title Fiji Automated Analysis GUI
echo Fiji Automated Analysis GUI
echo ===========================

set "APP_DIR=%~dp0"
set "VENV_DIR=%APP_DIR%.venv"
cd /d "%APP_DIR%"

if not exist "%APP_DIR%gui.py" (
    echo Error: gui.py was not found.
    echo Move this launcher back to the project folder and try again.
    goto fail
)

if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
    goto venv_ready
)

set "SYSTEM_PYTHON_EXE="
set "SYSTEM_PYTHON_ARGS="

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "SYSTEM_PYTHON_EXE=py"
    set "SYSTEM_PYTHON_ARGS=-3"
    goto system_python_found
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    set "SYSTEM_PYTHON_EXE=python"
    goto system_python_found
)

echo Error: Python is not installed or not in PATH.
echo Install Python 3.10 or newer and enable "Add python.exe to PATH".
goto fail

:system_python_found
"%SYSTEM_PYTHON_EXE%" %SYSTEM_PYTHON_ARGS% -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
if %ERRORLEVEL% neq 0 (
    echo Error: Python 3.10 or newer is required.
    goto fail
)

echo Creating local Python environment...
"%SYSTEM_PYTHON_EXE%" %SYSTEM_PYTHON_ARGS% -m venv "%VENV_DIR%"
if %ERRORLEVEL% neq 0 (
    echo Failed to create the Python environment.
    goto fail
)

set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

:venv_ready
"%PYTHON_EXE%" -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
if %ERRORLEVEL% neq 0 (
    echo Error: Python 3.10 or newer is required.
    echo Delete .venv and rerun this launcher after installing a newer Python.
    goto fail
)

echo Installing Python dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo Failed to upgrade pip.
    goto fail
)

"%PYTHON_EXE%" -m pip install -r "%APP_DIR%requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo Failed to install dependencies.
    goto fail
)

echo Starting GUI...
"%PYTHON_EXE%" -B "%APP_DIR%gui.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo GUI exited with code %EXIT_CODE%.
    goto fail
)

exit /b 0

:fail
echo.
echo Press any key to close this window.
pause >nul
exit /b 1
