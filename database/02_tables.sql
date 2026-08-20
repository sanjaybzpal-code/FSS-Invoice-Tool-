-- FSS Invoice & Accounts — tables
USE FSSInvoice;
GO

IF OBJECT_ID(N'dbo.ClientMaster', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ClientMaster (
        ClientId          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ClientName        NVARCHAR(200) NOT NULL,
        GSTIN             NVARCHAR(20)  NULL,
        Address           NVARCHAR(500) NULL,
        ContactPerson     NVARCHAR(100) NULL,
        Email             NVARCHAR(150) NULL,
        Mobile            NVARCHAR(20)  NULL,
        MhState           BIT NOT NULL DEFAULT 0,
        OpeningBalance    DECIMAL(18,2) NOT NULL DEFAULT 0,
        IsActive          BIT NOT NULL DEFAULT 1,
        CreatedAt         DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedAt         DATETIME2 NULL,
        CONSTRAINT UQ_ClientMaster_Name UNIQUE (ClientName)
    );
END
GO

IF OBJECT_ID(N'dbo.TaxInvoices', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TaxInvoices (
        InvoiceId         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ClientId          INT NOT NULL,
        InvoiceNumber     NVARCHAR(30) NOT NULL,
        InvoiceDate       DATE NOT NULL,
        TaxableAmount     DECIMAL(18,2) NOT NULL DEFAULT 0,
        CGSTAmount        DECIMAL(18,2) NOT NULL DEFAULT 0,
        SGSTAmount        DECIMAL(18,2) NOT NULL DEFAULT 0,
        IGSTAmount        DECIMAL(18,2) NOT NULL DEFAULT 0,
        TotalAmount       DECIMAL(18,2) NOT NULL,
        SupplyType        NVARCHAR(50) NULL,
        PdfPath           NVARCHAR(500) NULL,
        ExcelPath         NVARCHAR(500) NULL,
        CreatedBy         NVARCHAR(50) NULL,
        CreatedAt         DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_TaxInvoices_Client FOREIGN KEY (ClientId)
            REFERENCES dbo.ClientMaster(ClientId),
        CONSTRAINT UQ_TaxInvoices_Number UNIQUE (InvoiceNumber)
    );
    CREATE INDEX IX_TaxInvoices_ClientDate ON dbo.TaxInvoices(ClientId, InvoiceDate);
END
GO

IF OBJECT_ID(N'dbo.InvoiceLineItems', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.InvoiceLineItems (
        LineId            INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        InvoiceId         INT NOT NULL,
        SrNo              INT NOT NULL,
        Particulars       NVARCHAR(500) NOT NULL,
        WorkDate          DATE NULL,
        Amount            DECIMAL(18,2) NOT NULL,
        CONSTRAINT FK_InvoiceLineItems_Invoice FOREIGN KEY (InvoiceId)
            REFERENCES dbo.TaxInvoices(InvoiceId) ON DELETE CASCADE
    );
END
GO

IF OBJECT_ID(N'dbo.Receipts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Receipts (
        ReceiptId         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ClientId          INT NOT NULL,
        ReceiptNumber     NVARCHAR(30) NOT NULL,
        ReceiptDate       DATE NOT NULL,
        AmountReceived    DECIMAL(18,2) NOT NULL,
        PaymentMode       NVARCHAR(50) NOT NULL,
        ReferenceNumber   NVARCHAR(100) NULL,
        Remarks           NVARCHAR(500) NULL,
        CreatedBy         NVARCHAR(50) NULL,
        CreatedAt         DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Receipts_Client FOREIGN KEY (ClientId)
            REFERENCES dbo.ClientMaster(ClientId),
        CONSTRAINT UQ_Receipts_Number UNIQUE (ReceiptNumber)
    );
    CREATE INDEX IX_Receipts_ClientDate ON dbo.Receipts(ClientId, ReceiptDate);
END
GO

IF OBJECT_ID(N'dbo.LedgerSequence', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.LedgerSequence (
        SeqName   NVARCHAR(50) NOT NULL PRIMARY KEY,
        NextValue INT NOT NULL DEFAULT 1
    );
    INSERT INTO dbo.LedgerSequence (SeqName, NextValue) VALUES (N'RECEIPT', 1);
END
GO
