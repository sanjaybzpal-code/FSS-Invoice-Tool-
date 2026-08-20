-- Business segments, expenses, receipt-invoice allocations
USE FSSInvoice;
GO

-- Master: business segments (extensible without code changes)
IF OBJECT_ID(N'dbo.BusinessSegments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.BusinessSegments (
        BusinessSegmentId   INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        BusinessSegmentName NVARCHAR(100) NOT NULL,
        SegmentCode         NVARCHAR(30)  NULL,
        IsActive            BIT NOT NULL DEFAULT 1,
        SortOrder           INT NOT NULL DEFAULT 0,
        CreatedAt           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE UNIQUE INDEX UQ_BusinessSegments_Name ON dbo.BusinessSegments(BusinessSegmentName);
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.BusinessSegments WHERE BusinessSegmentName = N'FSS Calculation')
    INSERT INTO dbo.BusinessSegments (BusinessSegmentName, SegmentCode, SortOrder)
    VALUES (N'FSS Calculation', N'CALC', 1);
IF NOT EXISTS (SELECT 1 FROM dbo.BusinessSegments WHERE BusinessSegmentName = N'FSS Consultancy')
    INSERT INTO dbo.BusinessSegments (BusinessSegmentName, SegmentCode, SortOrder)
    VALUES (N'FSS Consultancy', N'CONSULT', 2);
IF NOT EXISTS (SELECT 1 FROM dbo.BusinessSegments WHERE BusinessSegmentName = N'Next Gen')
    INSERT INTO dbo.BusinessSegments (BusinessSegmentName, SegmentCode, SortOrder)
    VALUES (N'Next Gen', N'NEXTGEN', 3);
GO

-- Link invoices to segment (management reporting only)
IF COL_LENGTH('dbo.TaxInvoices', 'BusinessSegmentId') IS NULL
BEGIN
    ALTER TABLE dbo.TaxInvoices ADD BusinessSegmentId INT NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_TaxInvoices_Segment')
BEGIN
    ALTER TABLE dbo.TaxInvoices ADD CONSTRAINT FK_TaxInvoices_Segment
        FOREIGN KEY (BusinessSegmentId) REFERENCES dbo.BusinessSegments(BusinessSegmentId);
END
GO

IF COL_LENGTH('dbo.TaxInvoices', 'BusinessSegmentId') IS NOT NULL
BEGIN
    UPDATE dbo.TaxInvoices SET BusinessSegmentId = (
        SELECT TOP 1 BusinessSegmentId FROM dbo.BusinessSegments WHERE BusinessSegmentName = N'FSS Calculation'
    ) WHERE BusinessSegmentId IS NULL;
END
GO

-- Expense categories (admin can add more)
IF OBJECT_ID(N'dbo.ExpenseCategories', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ExpenseCategories (
        ExpenseCategoryId INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CategoryName      NVARCHAR(100) NOT NULL,
        IsActive          BIT NOT NULL DEFAULT 1,
        IsSystem          BIT NOT NULL DEFAULT 0,
        CreatedAt         DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE UNIQUE INDEX UQ_ExpenseCategories_Name ON dbo.ExpenseCategories(CategoryName);
END
GO

DECLARE @cats TABLE (n NVARCHAR(100));
INSERT INTO @cats VALUES
 (N'NextGen Software Infrastructure'),(N'Office Rent'),(N'Electricity'),
 (N'Maid / Housekeeping'),(N'Internet'),(N'Marketing'),(N'Travel'),(N'Hotel'),
 (N'Software Subscription'),(N'Consultant Fees'),(N'Salaries'),
 (N'Professional Fees'),(N'Miscellaneous');
INSERT INTO dbo.ExpenseCategories (CategoryName, IsSystem)
SELECT c.n, 1 FROM @cats c
WHERE NOT EXISTS (SELECT 1 FROM dbo.ExpenseCategories ec WHERE ec.CategoryName = c.n);
GO

-- Expenses (admin only)
IF OBJECT_ID(N'dbo.Expenses', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Expenses (
        ExpenseId           INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ExpenseDate         DATE NOT NULL,
        ExpenseCategoryId   INT NOT NULL,
        ExpenseDescription  NVARCHAR(500) NOT NULL,
        Amount              DECIMAL(18,2) NOT NULL,
        GstAmount           DECIMAL(18,2) NOT NULL DEFAULT 0,
        TotalAmount         AS (Amount + GstAmount) PERSISTED,
        VendorName          NVARCHAR(200) NULL,
        PaymentMode         NVARCHAR(50)  NULL,
        ReferenceNumber     NVARCHAR(100) NULL,
        Remarks             NVARCHAR(500) NULL,
        AllocationType      NVARCHAR(30) NOT NULL DEFAULT N'segment',
        -- segment | common_equal | common_revenue | common_manual
        BusinessSegmentId   INT NULL,
        CreatedBy           NVARCHAR(50) NULL,
        CreatedAt           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedAt           DATETIME2 NULL,
        CONSTRAINT FK_Expenses_Category FOREIGN KEY (ExpenseCategoryId)
            REFERENCES dbo.ExpenseCategories(ExpenseCategoryId),
        CONSTRAINT FK_Expenses_Segment FOREIGN KEY (BusinessSegmentId)
            REFERENCES dbo.BusinessSegments(BusinessSegmentId)
    );
    CREATE INDEX IX_Expenses_Date ON dbo.Expenses(ExpenseDate);
END
GO

-- Per-segment expense allocation (for common expenses and manual splits)
IF OBJECT_ID(N'dbo.ExpenseSegmentAllocations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ExpenseSegmentAllocations (
        AllocationId        INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ExpenseId           INT NOT NULL,
        BusinessSegmentId   INT NOT NULL,
        AllocatedAmount     DECIMAL(18,2) NOT NULL,
        AllocPercent        DECIMAL(7,4) NULL,
        CONSTRAINT FK_ExpAlloc_Expense FOREIGN KEY (ExpenseId)
            REFERENCES dbo.Expenses(ExpenseId) ON DELETE CASCADE,
        CONSTRAINT FK_ExpAlloc_Segment FOREIGN KEY (BusinessSegmentId)
            REFERENCES dbo.BusinessSegments(BusinessSegmentId)
    );
    CREATE INDEX IX_ExpAlloc_Expense ON dbo.ExpenseSegmentAllocations(ExpenseId);
END
GO

-- Receipt applied to invoices (segment derived from invoice)
IF OBJECT_ID(N'dbo.ReceiptInvoiceAllocations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ReceiptInvoiceAllocations (
        AllocationId        INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ReceiptId           INT NOT NULL,
        InvoiceId           INT NOT NULL,
        BusinessSegmentId   INT NOT NULL,
        AllocatedAmount     DECIMAL(18,2) NOT NULL,
        CONSTRAINT FK_RcpAlloc_Receipt FOREIGN KEY (ReceiptId)
            REFERENCES dbo.Receipts(ReceiptId) ON DELETE CASCADE,
        CONSTRAINT FK_RcpAlloc_Invoice FOREIGN KEY (InvoiceId)
            REFERENCES dbo.TaxInvoices(InvoiceId),
        CONSTRAINT FK_RcpAlloc_Segment FOREIGN KEY (BusinessSegmentId)
            REFERENCES dbo.BusinessSegments(BusinessSegmentId)
    );
    CREATE INDEX IX_RcpAlloc_Receipt ON dbo.ReceiptInvoiceAllocations(ReceiptId);
END
GO
