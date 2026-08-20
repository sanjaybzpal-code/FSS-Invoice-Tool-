@echo off
REM One-click internet live URL using Cloudflare Tunnel + local SQL Server.
cd /d "%~dp0"
set PYTHONUTF8=1
set VERCEL=
set VERCEL_ENV=
title FSS Invoice Tool — Internet Live

echo.
echo ============================================================
echo   FSS Invoice Tool — LIVE on Internet (Cloudflare)
echo ============================================================
echo.
echo This uses YOUR local SQL Server (all invoices + receipts).
echo No Azure SQL. No Vercel database.
echo Keep this window OPEN. Closing it stops the public URL.
echo.

REM Start local server if port 5000 is free
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo Starting local server on port 5000...
    start "FSS Invoice Tool Server" /MIN python run_live.py
    timeout /t 4 /nobreak >nul
) else (
    echo Server already running on port 5000.
)

if not exist "%~dp0cloudflared.exe" (
    echo Downloading Cloudflare tunnel...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%~dp0cloudflared.exe' -UseBasicParsing"
    if not exist "%~dp0cloudflared.exe" (
        echo Download failed. Open: https://github.com/cloudflare/cloudflared/releases
        echo Save cloudflared-windows-amd64.exe as cloudflared.exe in this folder.
        pause
        exit /b 1
    )
)

echo.
echo Opening a public URL... copy the https://....trycloudflare.com line below
echo and send it to the client. Login is still required.
echo.
echo ============================================================
"%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:5000
pause
