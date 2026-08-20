-- AR extensions: due dates, TDS, reminders, WhatsApp log, project costs, audit
USE FSSInvoice;
GO

-- Invoice due date / payment terms
IF COL_LENGTH('dbo.TaxInvoices', 'DueDate') IS NULL
    ALTER TABLE dbo.TaxInvoices ADD DueDate DATE NULL;
IF COL_LENGTH('dbo.TaxInvoices', 'PaymentTermsDays') IS NULL
    ALTER TABLE dbo.TaxInvoices ADD PaymentTermsDays INT NOT NULL DEFAULT 30;
GO

UPDATE dbo.TaxInvoices
SET DueDate = DATEADD(DAY, ISNULL(PaymentTermsDays, 30), InvoiceDate),
    PaymentTermsDays = ISNULL(PaymentTermsDays, 30)
WHERE DueDate IS NULL;
GO

-- TDS on receipts
IF COL_LENGTH('dbo.Receipts', 'InvoiceAmount') IS NULL
    ALTER TABLE dbo.Receipts ADD InvoiceAmount DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.Receipts', 'TdsPercentage') IS NULL
    ALTER TABLE dbo.Receipts ADD TdsPercentage DECIMAL(5,2) NOT NULL DEFAULT 0;
IF COL_LENGTH('dbo.Receipts', 'TdsAmount') IS NULL
    ALTER TABLE dbo.Receipts ADD TdsAmount DECIMAL(18,2) NOT NULL DEFAULT 0;
IF COL_LENGTH('dbo.Receipts', 'FinancialYear') IS NULL
    ALTER TABLE dbo.Receipts ADD FinancialYear NVARCHAR(10) NULL;
IF COL_LENGTH('dbo.Receipts', 'TdsCertificateReceived') IS NULL
    ALTER TABLE dbo.Receipts ADD TdsCertificateReceived BIT NOT NULL DEFAULT 0;
IF COL_LENGTH('dbo.Receipts', 'TdsCertificateNo') IS NULL
    ALTER TABLE dbo.Receipts ADD TdsCertificateNo NVARCHAR(50) NULL;
IF COL_LENGTH('dbo.Receipts', 'TdsCertificateDate') IS NULL
    ALTER TABLE dbo.Receipts ADD TdsCertificateDate DATE NULL;
GO

IF OBJECT_ID(N'dbo.ReminderHistory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ReminderHistory (
        ReminderId    INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        InvoiceId     INT NOT NULL,
        ClientId      INT NOT NULL,
        RuleType      NVARCHAR(30) NOT NULL,
        Channel       NVARCHAR(20) NOT NULL DEFAULT N'email',
        SentAt        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        Recipient     NVARCHAR(200) NOT NULL,
        DeliveryStatus NVARCHAR(50) NOT NULL DEFAULT N'sent',
        MessageBody   NVARCHAR(MAX) NULL,
        CreatedBy     NVARCHAR(50) NULL,
        CONSTRAINT FK_ReminderHistory_Invoice FOREIGN KEY (InvoiceId) REFERENCES dbo.TaxInvoices(InvoiceId),
        CONSTRAINT FK_ReminderHistory_Client FOREIGN KEY (ClientId) REFERENCES dbo.ClientMaster(ClientId)
    );
    CREATE INDEX IX_ReminderHistory_Invoice ON dbo.ReminderHistory(InvoiceId, RuleType, Channel);
END
GO

IF OBJECT_ID(N'dbo.WhatsAppLog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.WhatsAppLog (
        LogId         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ClientId      INT NOT NULL,
        InvoiceId     INT NULL,
        Mobile        NVARCHAR(20) NOT NULL,
        MessageType   NVARCHAR(30) NOT NULL,
        MessageBody   NVARCHAR(MAX) NULL,
        SentAt        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        SentBy        NVARCHAR(50) NULL,
        Status        NVARCHAR(50) NOT NULL DEFAULT N'initiated',
        CONSTRAINT FK_WhatsAppLog_Client FOREIGN KEY (ClientId) REFERENCES dbo.ClientMaster(ClientId)
    );
END
GO

IF OBJECT_ID(N'dbo.ProjectCosts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProjectCosts (
        CostId              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ClientId            INT NOT NULL,
        ProjectName         NVARCHAR(200) NOT NULL DEFAULT N'General',
        PeriodYear          INT NOT NULL,
        PeriodMonth         INT NOT NULL,
        Revenue             DECIMAL(18,2) NOT NULL DEFAULT 0,
        ConsultancyCharges  DECIMAL(18,2) NOT NULL DEFAULT 0,
        Manhours            DECIMAL(10,2) NOT NULL DEFAULT 0,
        EmployeeCost        DECIMAL(18,2) NOT NULL DEFAULT 0,
        TravelCost          DECIMAL(18,2) NOT NULL DEFAULT 0,
        MiscellaneousCost   DECIMAL(18,2) NOT NULL DEFAULT 0,
        Notes               NVARCHAR(500) NULL,
        CreatedAt           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedBy           NVARCHAR(50) NULL,
        CONSTRAINT FK_ProjectCosts_Client FOREIGN KEY (ClientId) REFERENCES dbo.ClientMaster(ClientId)
    );
    CREATE UNIQUE INDEX UQ_ProjectCosts ON dbo.ProjectCosts(ClientId, ProjectName, PeriodYear, PeriodMonth);
END
GO

IF OBJECT_ID(N'dbo.AuditLog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.AuditLog (
        AuditId       BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        UserName      NVARCHAR(50) NOT NULL,
        Action        NVARCHAR(100) NOT NULL,
        EntityType    NVARCHAR(50) NULL,
        EntityId      NVARCHAR(50) NULL,
        Details       NVARCHAR(MAX) NULL,
        IpAddress     NVARCHAR(50) NULL,
        CreatedAt     DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX IX_AuditLog_Created ON dbo.AuditLog(CreatedAt DESC);
END
GO
