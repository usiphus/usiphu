@echo off
setlocal
cd /d "%~dp0"

echo.
echo ==========================================
echo          USIPHU - Windows setup
echo ==========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python Launcher was not found.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
    echo During installation, enable the Python Launcher option.
    pause
    exit /b 1
)

py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3.11 or newer was not found.
    echo Install Python 3.11 or newer, then run this setup again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the local Python environment...
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
)

echo Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed

echo Installing USIPHU and its development/test dependencies...
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto :failed

echo.
echo Setup complete. Starting USIPHU...
call "%~dp0start_usiphu.bat"
exit /b %errorlevel%

:failed
echo.
echo Setup failed. Check the error above and your internet connection.
pause
exit /b 1
