@echo off
REM Launches the FSS Invoice Generator.
cd /d "%~dp0"
set PYTHONUTF8=1

REM Try the py launcher first, then fall back to python.
where py >nul 2>nul
if %errorlevel%==0 (
    py app.py
) else (
    python app.py
)

if %errorlevel% neq 0 (
    echo.
    echo The tool exited with an error. Make sure Python 3 is installed
    echo and that "openpyxl" is available ^(pip install openpyxl^).
    pause
)
