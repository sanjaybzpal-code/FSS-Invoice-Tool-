@echo off
REM Exposes your local FSS Invoice Tool on the internet via Cloudflare Tunnel (free).
REM Prerequisites:
REM   1. Live server must be running (run "Go Live.bat" or launch.pyw first)
REM   2. Download cloudflared: https://github.com/cloudflare/cloudflared/releases
REM      Place cloudflared.exe in this folder OR install it globally.

cd /d "%~dp0"

echo.
echo ============================================================
echo   FSS Invoice Tool — Internet Access (Cloudflare Tunnel)
echo ============================================================
echo.
echo STEP 1: Make sure the live server is running on port 5000
echo         (Run "Go Live.bat" or double-click the desktop shortcut)
echo.
echo STEP 2: This will create a temporary public URL (trycloudflare.com)
echo         Share that URL ONLY with your team — login is still required.
echo.
pause

set CF=
if exist "%~dp0cloudflared.exe" set CF=%~dp0cloudflared.exe
if not defined CF where cloudflared >nul 2>&1 && set CF=cloudflared

if not defined CF (
    echo.
    echo cloudflared.exe not found.
    echo Download from: https://github.com/cloudflare/cloudflared/releases
    echo Put cloudflared.exe in this folder and run again.
    echo.
    pause
    exit /b 1
)

echo Starting tunnel to http://127.0.0.1:5000 ...
echo Copy the https://....trycloudflare.com URL when it appears.
echo Press Ctrl+C to stop the tunnel.
echo.

"%CF%" tunnel --url http://127.0.0.1:5000
