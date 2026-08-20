@echo off
REM Sets up 24/7 live server + firewall + startup task
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_live.ps1"
pause
