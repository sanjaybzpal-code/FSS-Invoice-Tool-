@echo off
REM One-time installer: creates Desktop + Start Menu shortcuts (and optional auto-start).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_app.ps1"
