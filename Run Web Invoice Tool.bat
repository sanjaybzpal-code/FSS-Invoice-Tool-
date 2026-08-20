@echo off
REM Starts the FSS Invoice Generator web app on http://127.0.0.1:5000
cd /d "%~dp0"
set PYTHONUTF8=1

where py >nul 2>nul
if %errorlevel%==0 (
    py web.py
) else (
    python web.py
)

if %errorlevel% neq 0 (
    echo.
    echo The web server exited with an error. Make sure Python 3 is installed
    echo and dependencies are present:  pip install -r requirements.txt
    pause
)
