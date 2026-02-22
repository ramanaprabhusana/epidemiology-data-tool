@echo off
title Epidemiology Data Tool
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo No .venv found. Install: python -m venv .venv   then   .venv\Scripts\activate   then   pip install -r requirements.txt
    pause
    exit /b 1
)

REM Open browser after 2 seconds (server will be starting)
start /B cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

echo.
echo Epidemiology Data Tool is starting.
echo Browser will open at http://127.0.0.1:5000
echo Keep this window open while using the tool. Close it when done.
echo.
python app_web.py

pause
