@echo off
REM Connect Vercel to Azure SQL and copy your local invoices/receipts.
cd /d "%~dp0"
set PYTHONUTF8=1
title FSS — Setup Vercel Database

echo.
echo ============================================================
echo   FSS Invoice Tool — Vercel Database Setup
echo ============================================================
echo.
echo Vercel CANNOT use your local SQL Server "(local)".
echo You need Azure SQL (free tier) OR use Go Live.bat for office use.
echo.
echo STEP 1 — Create Azure SQL (one time, ~5 min)
echo   https://portal.azure.com  ^> Create SQL Database
echo   Server: e.g. fss-invoice.database.windows.net
echo   Database: FSSInvoice
echo   SQL login + password (remember these)
echo   Firewall: Allow Azure services = ON
echo.
echo STEP 2 — Enter your Azure SQL details below:
echo.

set /p AZURE_SQL_HOST=Azure server (e.g. xxx.database.windows.net): 
set /p AZURE_SQL_USER=SQL username: 
set /p AZURE_SQL_PASSWORD=SQL password: 
set AZURE_SQL_DATABASE=FSSInvoice

echo.
echo Syncing local data to Azure…
where py >nul 2>nul
if %errorlevel%==0 (
    py sync_local_to_azure.py
) else (
    python sync_local_to_azure.py
)

echo.
echo ============================================================
echo STEP 3 — Add these on Vercel (Settings ^> Environment Variables):
echo ============================================================
echo   AZURE_SQL_HOST=%AZURE_SQL_HOST%
echo   AZURE_SQL_USER=%AZURE_SQL_USER%
echo   AZURE_SQL_PASSWORD=(your password)
echo   AZURE_SQL_DATABASE=FSSInvoice
echo   FLASK_SECRET_KEY=(any random 64-char string)
echo   ADMIN_USERNAME=admin
echo   ADMIN_PASSWORD=(your login password)
echo.
echo   OR paste one line from Azure Portal:
echo   AZURE_SQL_CONNECTION_STRING=Server=tcp:...;Database=FSSInvoice;...
echo.
echo Opening Vercel settings…
start https://vercel.com/sanjaybzpal-codes-projects/fss-invoice-tool/settings/environment-variables
echo.
echo After saving env vars: Deployments ^> Redeploy
echo.
pause
