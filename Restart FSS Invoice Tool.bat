@echo off

REM Stops any old server and starts fresh (use after code updates)

cd /d "%~dp0"

echo Stopping old server on port 5000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr LISTENING') do (

    taskkill /F /PID %%a >nul 2>nul

)

timeout /t 2 /nobreak >nul

echo Starting FSS Invoice Tool...

start "" "%~dp0launch.pyw"

