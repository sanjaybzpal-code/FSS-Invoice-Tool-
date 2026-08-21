@echo off
REM Permanent 24/7 live: Azure SQL (free) + Vercel. Office PC OFF ho to bhi site chalti hai.
cd /d "%~dp0"
set PYTHONUTF8=1
title FSS — Always Live (24x7)

echo.
echo ============================================================
echo   FSS Invoice Tool — 24x7 LIVE (office PC band ho to bhi)
echo ============================================================
echo.
echo Office PC / Cloudflare tunnel 24 ghante ON nahi reh sakta.
echo Isliye cloud database chahiye: Azure SQL (FREE) + Vercel.
echo Permanent URL: https://fss-invoice-tool.vercel.app
echo.
echo --- Aapko 1 baar yeh karna hai (~10 min) ---
echo.
echo 1. Azure SQL FREE database banao (browser khulega)
echo    - "Start free" / "Apply offer" click karo
echo    - Database name: FSSInvoice
echo    - SQL admin login + password YAAD RAKHO
echo    - Networking: Allow Azure services = ON
echo    - Add your client IPv4 address (firewall)
echo.
echo 2. Yahan server / user / password type karo
echo    Script local invoices+receipts Azure par copy karega
echo.
echo 3. Wahi details Vercel Environment Variables mein paste
echo    phir Redeploy — site 24x7 live ho jayegi
echo.
pause

echo Opening Azure SQL (Start free) and Vercel settings...
start https://aka.ms/azuresqlhub
timeout /t 2 /nobreak >nul
start https://portal.azure.com/#create/Microsoft.SQLDatabase
timeout /t 1 /nobreak >nul
start https://vercel.com/sanjaybzpal-codes-projects/fss-invoice-tool/settings/environment-variables

echo.
echo Azure par database banane ke BAAD yahan details daalo.
echo Server example: fssinvoice.database.windows.net
echo.

set /p AZURE_SQL_HOST=Azure server name: 
set /p AZURE_SQL_USER=SQL username: 
set /p AZURE_SQL_PASSWORD=SQL password: 
if "%AZURE_SQL_DATABASE%"=="" set AZURE_SQL_DATABASE=FSSInvoice

if "%AZURE_SQL_HOST%"=="" (
    echo Server name khali hai. Azure banane ke baad dubara chalao.
    pause
    exit /b 1
)

echo.
echo Local data Azure par copy ho rahi hai...
where py >nul 2>nul
if %errorlevel%==0 (
    py sync_local_to_azure.py
) else (
    python sync_local_to_azure.py
)

echo.
echo ============================================================
echo Vercel par yeh 7 variables ADD karo (Production):
echo ============================================================
echo   AZURE_SQL_HOST=%AZURE_SQL_HOST%
echo   AZURE_SQL_USER=%AZURE_SQL_USER%
echo   AZURE_SQL_PASSWORD=(jo password abhi dala)
echo   AZURE_SQL_DATABASE=FSSInvoice
echo   FLASK_SECRET_KEY=FssLive-%RANDOM%%RANDOM%%RANDOM%
echo   ADMIN_USERNAME=admin
echo   ADMIN_PASSWORD=(aapki login password, min 6 chars)
echo.
echo Save ke baad: Vercel ^> Deployments ^> ... ^> Redeploy
echo Phir client ko bhejo: https://fss-invoice-tool.vercel.app
echo.
echo Naye invoices ke baad yeh file dubara chalao taaki cloud update ho.
echo.
pause
