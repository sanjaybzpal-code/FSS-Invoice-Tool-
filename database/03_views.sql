-- FSS Invoice & Accounts — views
USE FSSInvoice;
GO

CREATE OR ALTER VIEW dbo.vw_ClientLedger AS
-- Opening balance (debit if positive receivable)
SELECT
    c.ClientId,
    CAST('1900-01-01' AS DATE) AS TxnDate,
    N'OPEN' AS VoucherNo,
    N'Opening Balance' AS Particulars,
    CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END AS Debit,
    CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END AS Credit,
    0 AS SortOrder
FROM dbo.ClientMaster c
WHERE c.OpeningBalance <> 0

UNION ALL

-- Invoice = Debit (amount receivable from client)
SELECT
    i.ClientId,
    i.InvoiceDate,
    i.InvoiceNumber,
    N'Tax Invoice ' + i.InvoiceNumber,
    i.TotalAmount,
    0,
    1
FROM dbo.TaxInvoices i

UNION ALL

-- Receipt = Credit (payment received)
SELECT
    r.ClientId,
    r.ReceiptDate,
    r.ReceiptNumber,
    N'Receipt ' + r.ReceiptNumber
        + CASE WHEN r.PaymentMode IS NOT NULL THEN N' (' + r.PaymentMode + N')' ELSE N'' END,
    0,
    r.AmountReceived,
    2
FROM dbo.Receipts r;
GO

CREATE OR ALTER VIEW dbo.vw_ClientOutstanding AS
SELECT
    c.ClientId,
    c.ClientName,
    c.GSTIN,
    ISNULL(inv.TotalInvoiced, 0) + CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END AS TotalInvoiced,
    ISNULL(rcpt.TotalReceived, 0) + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END AS TotalReceived,
    (ISNULL(inv.TotalInvoiced, 0) + CASE WHEN c.OpeningBalance > 0 THEN c.OpeningBalance ELSE 0 END)
        - (ISNULL(rcpt.TotalReceived, 0) + CASE WHEN c.OpeningBalance < 0 THEN ABS(c.OpeningBalance) ELSE 0 END) AS Outstanding,
    inv.LastInvoiceDate,
    rcpt.LastPaymentDate
FROM dbo.ClientMaster c
LEFT JOIN (
    SELECT ClientId, SUM(TotalAmount) AS TotalInvoiced, MAX(InvoiceDate) AS LastInvoiceDate
    FROM dbo.TaxInvoices GROUP BY ClientId
) inv ON inv.ClientId = c.ClientId
LEFT JOIN (
    SELECT ClientId, SUM(AmountReceived) AS TotalReceived, MAX(ReceiptDate) AS LastPaymentDate
    FROM dbo.Receipts GROUP BY ClientId
) rcpt ON rcpt.ClientId = c.ClientId
WHERE c.IsActive = 1;
GO

CREATE OR ALTER VIEW dbo.vw_OutstandingDashboard AS
SELECT
    SUM(TotalInvoiced) AS TotalInvoiced,
    SUM(TotalReceived) AS TotalReceived,
    SUM(Outstanding) AS TotalOutstanding,
    SUM(CASE WHEN Outstanding > 0 THEN 1 ELSE 0 END) AS OutstandingClientCount
FROM dbo.vw_ClientOutstanding;
GO

CREATE OR ALTER VIEW dbo.vw_InvoiceAgeing AS
SELECT
    i.ClientId,
    c.ClientName,
    i.InvoiceId,
    i.InvoiceNumber,
    i.InvoiceDate,
    i.TotalAmount,
    ISNULL(alloc.PaidAgainstInvoice, 0) AS PaidAmount,
    i.TotalAmount - ISNULL(alloc.PaidAgainstInvoice, 0) AS PendingAmount,
    DATEDIFF(DAY, i.InvoiceDate, CAST(GETDATE() AS DATE)) AS AgeDays,
    CASE
        WHEN DATEDIFF(DAY, i.InvoiceDate, CAST(GETDATE() AS DATE)) <= 30 THEN N'0-30 Days'
        WHEN DATEDIFF(DAY, i.InvoiceDate, CAST(GETDATE() AS DATE)) <= 60 THEN N'31-60 Days'
        WHEN DATEDIFF(DAY, i.InvoiceDate, CAST(GETDATE() AS DATE)) <= 90 THEN N'61-90 Days'
        ELSE N'Above 90 Days'
    END AS AgeBucket
FROM dbo.TaxInvoices i
INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
LEFT JOIN (
    -- Proportional allocation: receipts applied FIFO per client (simplified)
    SELECT i2.InvoiceId,
           CASE
               WHEN client_rcpt.TotalReceived >= client_inv.CumTotal
               THEN i2.TotalAmount
               WHEN client_rcpt.TotalReceived <= client_inv.CumTotal - i2.TotalAmount
               THEN 0
               ELSE client_rcpt.TotalReceived - (client_inv.CumTotal - i2.TotalAmount)
           END AS PaidAgainstInvoice
    FROM dbo.TaxInvoices i2
    INNER JOIN (
        SELECT InvoiceId, ClientId, TotalAmount,
               SUM(TotalAmount) OVER (PARTITION BY ClientId ORDER BY InvoiceDate, InvoiceId) AS CumTotal
        FROM dbo.TaxInvoices
    ) client_inv ON client_inv.InvoiceId = i2.InvoiceId
    INNER JOIN (
        SELECT ClientId, SUM(AmountReceived) AS TotalReceived FROM dbo.Receipts GROUP BY ClientId
    ) client_rcpt ON client_rcpt.ClientId = i2.ClientId
) alloc ON alloc.InvoiceId = i.InvoiceId
WHERE i.TotalAmount - ISNULL(alloc.PaidAgainstInvoice, 0) > 0.01;
GO
