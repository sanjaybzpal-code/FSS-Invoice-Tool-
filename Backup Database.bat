@echo off
REM Backup FSSInvoice database to C:\FSS_Backups
set BACKUP_DIR=C:\FSS_Backups
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
set FILE=%BACKUP_DIR%\FSSInvoice_%date:~-4,4%%date:~-10,2%%date:~-7,2%.bak
echo Backing up to %FILE% ...
sqlcmd -S (local) -E -Q "BACKUP DATABASE FSSInvoice TO DISK='%FILE%' WITH INIT, COMPRESSION"
if %errorlevel%==0 (echo Backup successful.) else (echo Backup failed. Is SQL Server running?)
pause
