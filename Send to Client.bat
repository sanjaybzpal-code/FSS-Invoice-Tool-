@echo off
REM Creates FSS-Invoice-Tool-Client-Package.zip in the parent folder — ready to email/USB.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_client_package.ps1"
pause
