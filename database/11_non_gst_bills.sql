-- Non-GST bills (cash / without GST) — separate from tax invoices
USE FSSInvoice;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.LedgerSequence WHERE SeqName = N'NONGST')
    INSERT INTO dbo.LedgerSequence (SeqName, NextValue) VALUES (N'NONGST', 1);
GO

IF OBJECT_ID(N'dbo.NonGstBills', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.NonGstBills (
        NonGstBillId      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ClientId          INT NOT NULL,
        BillNumber        NVARCHAR(30) NOT NULL,
        BillDate          DATE NOT NULL,
        Amount            DECIMAL(18,2) NOT NULL,
        Description       NVARCHAR(500) NOT NULL,
        BusinessSegmentId INT NULL,
        Remarks           NVARCHAR(500) NULL,
        CreatedBy         NVARCHAR(50) NULL,
        CreatedAt         DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_NonGstBills_Client FOREIGN KEY (ClientId)
            REFERENCES dbo.ClientMaster(ClientId),
        CONSTRAINT FK_NonGstBills_Segment FOREIGN KEY (BusinessSegmentId)
            REFERENCES dbo.BusinessSegments(BusinessSegmentId),
        CONSTRAINT UQ_NonGstBills_Number UNIQUE (BillNumber)
    );
    CREATE INDEX IX_NonGstBills_ClientDate ON dbo.NonGstBills(ClientId, BillDate);
END
GO

IF OBJECT_ID(N'dbo.ReceiptNonGstAllocations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ReceiptNonGstAllocations (
        AllocationId        INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ReceiptId           INT NOT NULL,
        NonGstBillId        INT NOT NULL,
        BusinessSegmentId   INT NOT NULL,
        AllocatedAmount     DECIMAL(18,2) NOT NULL,
        CONSTRAINT FK_RcpNonGst_Receipt FOREIGN KEY (ReceiptId)
            REFERENCES dbo.Receipts(ReceiptId) ON DELETE CASCADE,
        CONSTRAINT FK_RcpNonGst_Bill FOREIGN KEY (NonGstBillId)
            REFERENCES dbo.NonGstBills(NonGstBillId),
        CONSTRAINT FK_RcpNonGst_Segment FOREIGN KEY (BusinessSegmentId)
            REFERENCES dbo.BusinessSegments(BusinessSegmentId)
    );
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_NextNonGstBillNumber
    @NextNumber NVARCHAR(30) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @n INT;
    UPDATE dbo.LedgerSequence WITH (ROWLOCK)
    SET @n = NextValue, NextValue = NextValue + 1
    WHERE SeqName = N'NONGST';
    SET @NextNumber = N'NGB-' + RIGHT(N'00000' + CAST(@n AS NVARCHAR), 5);
END
GO

-- Ledger view: tax invoices + non-GST bills + receipts
CREATE OR ALTER VIEW dbo.vw_ClientLedger AS
SELECT
    c.ClientId,
    CAST('1900-01-01' AS DATE) AS TxnDate,
    N'OPEN' AS VoucherNo,
    N'Opening Balance' AS Particulars,
    CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END AS Debit,
    CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END AS Credit,
    0 AS SortOrder,
    N'open' AS EntryType
FROM dbo.ClientMaster c
WHERE c.OpeningBalance <> 0

UNION ALL

SELECT
    i.ClientId, i.InvoiceDate, i.InvoiceNumber,
    N'Tax Invoice ' + i.InvoiceNumber,
    i.TotalAmount, 0, 1, N'tax'
FROM dbo.TaxInvoices i

UNION ALL

SELECT
    n.ClientId, n.BillDate, n.BillNumber,
    N'Non GST Bill ' + n.BillNumber + N' — ' + LEFT(n.Description, 80),
    n.Amount, 0, 1, N'nongst'
FROM dbo.NonGstBills n

UNION ALL

SELECT
    r.ClientId, r.ReceiptDate, r.ReceiptNumber,
    N'Receipt ' + r.ReceiptNumber
        + CASE WHEN r.PaymentMode IS NOT NULL THEN N' (' + r.PaymentMode + N')' ELSE N'' END,
    0, r.AmountReceived, 2, N'receipt'
FROM dbo.Receipts r;
GO

CREATE OR ALTER VIEW dbo.vw_ClientOutstanding AS
SELECT
    c.ClientId,
    c.ClientName,
    c.GSTIN,
    ISNULL(tax.TotalTaxInvoiced, 0) AS TotalTaxInvoiced,
    ISNULL(ng.TotalNonGstBilled, 0) AS TotalNonGstBilled,
    ISNULL(tax.TotalTaxInvoiced, 0) + ISNULL(ng.TotalNonGstBilled, 0)
        + CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END AS TotalInvoiced,
    ISNULL(rcpt.TotalReceived, 0)
        + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END AS TotalReceived,
    (ISNULL(tax.TotalTaxInvoiced, 0) + ISNULL(ng.TotalNonGstBilled, 0)
        + CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END)
        - (ISNULL(rcpt.TotalReceived, 0)
        + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END) AS Outstanding,
    tax.LastTaxInvoiceDate AS LastInvoiceDate,
    ng.LastNonGstDate AS LastNonGstDate,
    rcpt.LastPaymentDate AS LastPaymentDate
FROM dbo.ClientMaster c
LEFT JOIN (
    SELECT ClientId, SUM(TotalAmount) AS TotalTaxInvoiced, MAX(InvoiceDate) AS LastTaxInvoiceDate
    FROM dbo.TaxInvoices GROUP BY ClientId
) tax ON tax.ClientId = c.ClientId
LEFT JOIN (
    SELECT ClientId, SUM(Amount) AS TotalNonGstBilled, MAX(BillDate) AS LastNonGstDate
    FROM dbo.NonGstBills GROUP BY ClientId
) ng ON ng.ClientId = c.ClientId
LEFT JOIN (
    SELECT ClientId, SUM(AmountReceived) AS TotalReceived, MAX(ReceiptDate) AS LastPaymentDate
    FROM dbo.Receipts GROUP BY ClientId
) rcpt ON rcpt.ClientId = c.ClientId
WHERE c.IsActive = 1;
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetClientLedger
    @ClientId INT,
    @FromDate DATE = NULL,
    @ToDate   DATE = NULL,
    @BusinessSegmentId INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @FromDate IS NULL SET @FromDate = '1900-01-01';
    IF @ToDate IS NULL SET @ToDate = '9999-12-31';

    ;WITH Ledger AS (
        SELECT l.TxnDate, l.VoucherNo, l.Particulars, l.Debit, l.Credit, l.SortOrder, l.EntryType
        FROM dbo.vw_ClientLedger l
        WHERE l.ClientId = @ClientId
          AND l.TxnDate BETWEEN @FromDate AND @ToDate
          AND (@BusinessSegmentId IS NULL OR l.SortOrder = 0
               OR EXISTS (
                   SELECT 1 FROM dbo.TaxInvoices ti
                   WHERE ti.InvoiceNumber = l.VoucherNo AND ti.BusinessSegmentId = @BusinessSegmentId
               )
               OR EXISTS (
                   SELECT 1 FROM dbo.NonGstBills nb
                   WHERE nb.BillNumber = l.VoucherNo AND nb.BusinessSegmentId = @BusinessSegmentId
               )
               OR EXISTS (
                   SELECT 1 FROM dbo.Receipts r
                   INNER JOIN dbo.ReceiptInvoiceAllocations ria ON ria.ReceiptId = r.ReceiptId
                   WHERE r.ReceiptNumber = l.VoucherNo AND ria.BusinessSegmentId = @BusinessSegmentId
               )
               OR EXISTS (
                   SELECT 1 FROM dbo.Receipts r
                   INNER JOIN dbo.ReceiptNonGstAllocations rng ON rng.ReceiptId = r.ReceiptId
                   WHERE r.ReceiptNumber = l.VoucherNo AND rng.BusinessSegmentId = @BusinessSegmentId
               ))
    ),
    Running AS (
        SELECT TxnDate, VoucherNo, Particulars, Debit, Credit,
            SUM(Debit - Credit) OVER (ORDER BY TxnDate, SortOrder, VoucherNo
                ROWS UNBOUNDED PRECEDING) AS RunningBalance
        FROM Ledger
    )
    SELECT TxnDate AS [Date], VoucherNo, Particulars, Debit, Credit, RunningBalance
    FROM Running
    ORDER BY TxnDate, VoucherNo;
END
GO
