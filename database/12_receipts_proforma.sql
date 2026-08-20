-- Receipt enhancements (TDS on net, GST tracking) + Proforma invoices
USE FSSInvoice;
GO

-- Receipt: taxable base, GST paid tracking, manual TDS
IF COL_LENGTH('dbo.Receipts', 'TaxableAmount') IS NULL
    ALTER TABLE dbo.Receipts ADD TaxableAmount DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.Receipts', 'GstAmount') IS NULL
    ALTER TABLE dbo.Receipts ADD GstAmount DECIMAL(18,2) NOT NULL DEFAULT 0;
IF COL_LENGTH('dbo.Receipts', 'GstPaidAmount') IS NULL
    ALTER TABLE dbo.Receipts ADD GstPaidAmount DECIMAL(18,2) NOT NULL DEFAULT 0;
IF COL_LENGTH('dbo.Receipts', 'GstPaidStatus') IS NULL
    ALTER TABLE dbo.Receipts ADD GstPaidStatus NVARCHAR(20) NULL DEFAULT N'unknown';
IF COL_LENGTH('dbo.Receipts', 'TdsManual') IS NULL
    ALTER TABLE dbo.Receipts ADD TdsManual BIT NOT NULL DEFAULT 0;
GO

UPDATE dbo.Receipts
SET TaxableAmount = ISNULL(TaxableAmount, InvoiceAmount)
WHERE TaxableAmount IS NULL AND InvoiceAmount IS NOT NULL;
GO

-- Proforma vs Tax invoice
IF COL_LENGTH('dbo.TaxInvoices', 'InvoiceType') IS NULL
    ALTER TABLE dbo.TaxInvoices ADD InvoiceType NVARCHAR(20) NOT NULL DEFAULT N'TAX';
IF COL_LENGTH('dbo.TaxInvoices', 'ConvertedFromInvoiceId') IS NULL
    ALTER TABLE dbo.TaxInvoices ADD ConvertedFromInvoiceId INT NULL;
GO

UPDATE dbo.TaxInvoices SET InvoiceType = N'TAX' WHERE InvoiceType IS NULL OR InvoiceType = N'';
GO

IF NOT EXISTS (SELECT 1 FROM dbo.LedgerSequence WHERE SeqName = N'PROFORMA')
    INSERT INTO dbo.LedgerSequence (SeqName, NextValue) VALUES (N'PROFORMA', 1);
GO

CREATE OR ALTER PROCEDURE dbo.sp_NextProformaNumber
    @NextNumber NVARCHAR(30) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @n INT;
    UPDATE dbo.LedgerSequence WITH (ROWLOCK)
    SET @n = NextValue, NextValue = NextValue + 1
    WHERE SeqName = N'PROFORMA';
    SET @NextNumber = N'PF-' + RIGHT(N'00000' + CAST(@n AS NVARCHAR), 5);
END
GO

-- Client outstanding: TDS + GST bifurcation; exclude proforma from billed
CREATE OR ALTER VIEW dbo.vw_ClientOutstanding AS
SELECT
    c.ClientId,
    c.ClientName,
    c.GSTIN,
    ISNULL(tax.TotalTaxInvoiced, 0) AS TotalTaxInvoiced,
    ISNULL(ng.TotalNonGstBilled, 0) AS TotalNonGstBilled,
    ISNULL(tax.TotalGstInvoiced, 0) AS TotalGstInvoiced,
    ISNULL(tax.TotalTaxInvoiced, 0) + ISNULL(ng.TotalNonGstBilled, 0)
        + CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END AS TotalInvoiced,
    ISNULL(rcpt.TotalCashReceived, 0)
        + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END AS TotalReceived,
    ISNULL(rcpt.TotalTdsDeducted, 0) AS TotalTdsDeducted,
    ISNULL(rcpt.TotalGstPaid, 0) AS TotalGstPaid,
    ISNULL(rcpt.TotalCashReceived, 0) + ISNULL(rcpt.TotalTdsDeducted, 0)
        + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END AS EffectiveReceived,
    (ISNULL(tax.TotalTaxInvoiced, 0) + ISNULL(ng.TotalNonGstBilled, 0)
        + CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END)
        - (ISNULL(rcpt.TotalCashReceived, 0) + ISNULL(rcpt.TotalTdsDeducted, 0)
        + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END) AS Outstanding,
    ISNULL(tax.TotalGstInvoiced, 0) - ISNULL(rcpt.TotalGstPaid, 0) AS GstOutstanding,
    tax.LastTaxInvoiceDate AS LastInvoiceDate,
    ng.LastNonGstDate AS LastNonGstDate,
    rcpt.LastPaymentDate AS LastPaymentDate
FROM dbo.ClientMaster c
LEFT JOIN (
    SELECT ClientId,
           SUM(TotalAmount) AS TotalTaxInvoiced,
           SUM(CGSTAmount + SGSTAmount + IGSTAmount) AS TotalGstInvoiced,
           MAX(InvoiceDate) AS LastTaxInvoiceDate
    FROM dbo.TaxInvoices
    WHERE ISNULL(InvoiceType, N'TAX') <> N'PROFORMA'
    GROUP BY ClientId
) tax ON tax.ClientId = c.ClientId
LEFT JOIN (
    SELECT ClientId, SUM(Amount) AS TotalNonGstBilled, MAX(BillDate) AS LastNonGstDate
    FROM dbo.NonGstBills GROUP BY ClientId
) ng ON ng.ClientId = c.ClientId
LEFT JOIN (
    SELECT ClientId,
           SUM(AmountReceived) AS TotalCashReceived,
           SUM(TdsAmount) AS TotalTdsDeducted,
           SUM(GstPaidAmount) AS TotalGstPaid,
           MAX(ReceiptDate) AS LastPaymentDate
    FROM dbo.Receipts GROUP BY ClientId
) rcpt ON rcpt.ClientId = c.ClientId
WHERE c.IsActive = 1;
GO

CREATE OR ALTER VIEW dbo.vw_OutstandingDashboard AS
SELECT
    SUM(TotalInvoiced) AS TotalInvoiced,
    SUM(TotalReceived) AS TotalReceived,
    SUM(TotalTdsDeducted) AS TotalTdsDeducted,
    SUM(EffectiveReceived) AS TotalEffectiveReceived,
    SUM(Outstanding) AS TotalOutstanding,
    SUM(GstOutstanding) AS TotalGstOutstanding,
    SUM(CASE WHEN Outstanding > 0 THEN 1 ELSE 0 END) AS OutstandingClientCount
FROM dbo.vw_ClientOutstanding;
GO

-- Ledger: tax invoices (not proforma) + non-GST + receipts + TDS credits
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
WHERE ISNULL(i.InvoiceType, N'TAX') <> N'PROFORMA'

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
FROM dbo.Receipts r

UNION ALL

SELECT
    r.ClientId, r.ReceiptDate, r.ReceiptNumber,
    N'TDS deducted — ' + r.ReceiptNumber,
    0, r.TdsAmount, 2, N'tds'
FROM dbo.Receipts r
WHERE r.TdsAmount > 0;
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
                   WHERE ti.InvoiceNumber = l.VoucherNo
                     AND ISNULL(ti.InvoiceType, N'TAX') <> N'PROFORMA'
                     AND ti.BusinessSegmentId = @BusinessSegmentId
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
               )
               OR EXISTS (
                   SELECT 1 FROM dbo.Receipts r
                   WHERE r.ReceiptNumber = l.VoucherNo AND r.TdsAmount > 0
                     AND (l.EntryType = N'tds' OR l.EntryType = N'receipt')
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
