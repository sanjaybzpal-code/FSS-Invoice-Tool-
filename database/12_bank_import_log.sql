-- FSS Invoice: Bank Import Log table
USE FSSInvoice;
GO

IF OBJECT_ID(N'dbo.BankImportLog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.BankImportLog (
        ImportId        INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        FileName        NVARCHAR(200)      NOT NULL,
        BankDetected    NVARCHAR(50)       NULL,
        ImportedBy      NVARCHAR(50)       NULL,
        ImportedAt      DATETIME2          NOT NULL DEFAULT SYSUTCDATETIME(),
        RowsTotal       INT                NOT NULL DEFAULT 0,
        RowsImported    INT                NOT NULL DEFAULT 0,
        RowsSkipped     INT                NOT NULL DEFAULT 0,
        RowsError       INT                NOT NULL DEFAULT 0
    );
    CREATE INDEX IX_BankImportLog_Date ON dbo.BankImportLog(ImportedAt DESC);
    PRINT 'Created dbo.BankImportLog';
END
ELSE
    PRINT 'dbo.BankImportLog already exists — skipped.';
GO
