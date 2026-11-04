@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo USIPHU has not been installed on this computer yet.
    echo Double-click setup_windows.bat first.
    pause
    exit /b 1
)

echo Starting USIPHU...
echo Keep this window open while using the app.
echo The browser should open at http://localhost:8501
echo Press Ctrl+C in this window to stop USIPHU.
echo.

".venv\Scripts\python.exe" -m streamlit run app/Home.py
