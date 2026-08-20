-- Backup / restore helpers (run via sqlcmd or SSMS)
-- Backup:  sqlcmd -S (local) -E -Q "BACKUP DATABASE FSSInvoice TO DISK='C:\FSS_Backups\FSSInvoice.bak' WITH INIT"
-- Restore: sqlcmd -S (local) -E -Q "RESTORE DATABASE FSSInvoice FROM DISK='C:\FSS_Backups\FSSInvoice.bak' WITH REPLACE"

USE master;
GO

PRINT 'Use Backup Database.bat from the application folder for automated backups.';
GO
