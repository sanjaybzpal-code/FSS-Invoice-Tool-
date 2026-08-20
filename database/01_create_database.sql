-- FSS Invoice & Accounts — create database (run once as sysadmin)
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = N'FSSInvoice')
BEGIN
    CREATE DATABASE FSSInvoice;
END
GO

USE FSSInvoice;
GO
