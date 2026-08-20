-- Segment reporting views and stored procedures
USE FSSInvoice;
GO

CREATE OR ALTER VIEW dbo.vw_SegmentRevenue AS
SELECT
    s.BusinessSegmentId,
    s.BusinessSegmentName,
    ISNULL(SUM(i.TotalAmount), 0) AS TotalRevenue,
    COUNT(DISTINCT i.ClientId) AS ClientCount,
    COUNT(i.InvoiceId) AS InvoiceCount
FROM dbo.BusinessSegments s
LEFT JOIN dbo.TaxInvoices i ON i.BusinessSegmentId = s.BusinessSegmentId
WHERE s.IsActive = 1
GROUP BY s.BusinessSegmentId, s.BusinessSegmentName, s.SortOrder;
GO

CREATE OR ALTER VIEW dbo.vw_SegmentCollections AS
SELECT
    s.BusinessSegmentId,
    s.BusinessSegmentName,
    ISNULL(SUM(a.AllocatedAmount), 0) AS TotalCollected
FROM dbo.BusinessSegments s
LEFT JOIN dbo.ReceiptInvoiceAllocations a ON a.BusinessSegmentId = s.BusinessSegmentId
WHERE s.IsActive = 1
GROUP BY s.BusinessSegmentId, s.BusinessSegmentName;
GO

CREATE OR ALTER VIEW dbo.vw_SegmentOutstanding AS
SELECT
    s.BusinessSegmentId,
    s.BusinessSegmentName,
    ISNULL(rev.TotalRevenue, 0) AS TotalRevenue,
    ISNULL(col.TotalCollected, 0) AS TotalCollected,
    ISNULL(rev.TotalRevenue, 0) - ISNULL(col.TotalCollected, 0) AS Outstanding,
    ISNULL(rev.ClientCount, 0) AS ClientCount
FROM dbo.BusinessSegments s
LEFT JOIN dbo.vw_SegmentRevenue rev ON rev.BusinessSegmentId = s.BusinessSegmentId
LEFT JOIN dbo.vw_SegmentCollections col ON col.BusinessSegmentId = s.BusinessSegmentId
WHERE s.IsActive = 1;
GO

CREATE OR ALTER VIEW dbo.vw_SegmentExpenseAllocated AS
-- Direct segment expenses + allocated portions of common expenses
SELECT e.ExpenseId, e.ExpenseDate, e.ExpenseCategoryId,
       ec.CategoryName, e.ExpenseDescription, e.VendorName,
       s.BusinessSegmentId, s.BusinessSegmentName,
       CASE
           WHEN e.AllocationType = N'segment' THEN e.TotalAmount
           ELSE esa.AllocatedAmount
       END AS AllocatedAmount
FROM dbo.Expenses e
INNER JOIN dbo.ExpenseCategories ec ON ec.ExpenseCategoryId = e.ExpenseCategoryId
LEFT JOIN dbo.ExpenseSegmentAllocations esa ON esa.ExpenseId = e.ExpenseId
LEFT JOIN dbo.BusinessSegments s ON s.BusinessSegmentId = COALESCE(esa.BusinessSegmentId, e.BusinessSegmentId)
WHERE s.BusinessSegmentId IS NOT NULL;
GO

CREATE OR ALTER VIEW dbo.vw_SegmentProfitability AS
SELECT
    s.BusinessSegmentId,
    s.BusinessSegmentName,
    ISNULL(rev.TotalRevenue, 0) AS Revenue,
    ISNULL(exp.TotalExpense, 0) AS Expense,
    ISNULL(rev.TotalRevenue, 0) - ISNULL(exp.TotalExpense, 0) AS Profit,
    CASE WHEN ISNULL(rev.TotalRevenue, 0) > 0
         THEN ROUND((ISNULL(rev.TotalRevenue, 0) - ISNULL(exp.TotalExpense, 0))
              * 100.0 / rev.TotalRevenue, 2)
         ELSE 0 END AS ProfitPercent
FROM dbo.BusinessSegments s
LEFT JOIN dbo.vw_SegmentRevenue rev ON rev.BusinessSegmentId = s.BusinessSegmentId
LEFT JOIN (
    SELECT BusinessSegmentId, SUM(AllocatedAmount) AS TotalExpense
    FROM dbo.vw_SegmentExpenseAllocated
    GROUP BY BusinessSegmentId
) exp ON exp.BusinessSegmentId = s.BusinessSegmentId
WHERE s.IsActive = 1;
GO

CREATE OR ALTER VIEW dbo.vw_SegmentMonthlyRevenue AS
SELECT
    i.BusinessSegmentId,
    s.BusinessSegmentName,
    YEAR(i.InvoiceDate) AS PeriodYear,
    MONTH(i.InvoiceDate) AS PeriodMonth,
    SUM(i.TotalAmount) AS Revenue
FROM dbo.TaxInvoices i
INNER JOIN dbo.BusinessSegments s ON s.BusinessSegmentId = i.BusinessSegmentId
GROUP BY i.BusinessSegmentId, s.BusinessSegmentName, YEAR(i.InvoiceDate), MONTH(i.InvoiceDate);
GO

CREATE OR ALTER VIEW dbo.vw_SegmentMonthlyExpense AS
SELECT
    BusinessSegmentId,
    BusinessSegmentName,
    YEAR(ExpenseDate) AS PeriodYear,
    MONTH(ExpenseDate) AS PeriodMonth,
    SUM(AllocatedAmount) AS Expense
FROM dbo.vw_SegmentExpenseAllocated
GROUP BY BusinessSegmentId, BusinessSegmentName, YEAR(ExpenseDate), MONTH(ExpenseDate);
GO

CREATE OR ALTER VIEW dbo.vw_ExecutiveDashboard AS
SELECT
    ISNULL(SUM(i.TotalAmount), 0) AS TotalInvoiced,
    ISNULL((SELECT SUM(AmountReceived) FROM dbo.Receipts), 0) AS TotalReceived,
    ISNULL(SUM(i.TotalAmount), 0) - ISNULL((SELECT SUM(AmountReceived) FROM dbo.Receipts), 0) AS TotalOutstanding,
    ISNULL(SUM(i.CGSTAmount + i.SGSTAmount + i.IGSTAmount), 0) AS TotalGstReceivable,
    ISNULL((SELECT SUM(TdsAmount) FROM dbo.Receipts), 0) AS TotalTdsDeducted,
    (SELECT COUNT(*) FROM dbo.ClientMaster WHERE IsActive = 1) AS TotalActiveClients,
    ISNULL((SELECT SUM(TotalAmount) FROM dbo.Expenses), 0) AS TotalExpenses,
    ISNULL(SUM(i.TotalAmount), 0) - ISNULL((SELECT SUM(TotalAmount) FROM dbo.Expenses), 0) AS TotalProfit
FROM dbo.TaxInvoices i;
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetSegmentDashboard
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.vw_SegmentOutstanding ORDER BY BusinessSegmentId;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetSegmentProfitability
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.vw_SegmentProfitability ORDER BY BusinessSegmentId;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetSegmentMonthlyTrend
    @Months INT = 12
AS
BEGIN
    SET NOCOUNT ON;
    ;WITH Months AS (
        SELECT TOP (@Months)
            YEAR(DATEADD(MONTH, -ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) + 1, GETDATE())) AS Y,
            MONTH(DATEADD(MONTH, -ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) + 1, GETDATE())) AS M
        FROM sys.all_objects
    )
    SELECT
        s.BusinessSegmentId,
        s.BusinessSegmentName,
        mo.Y AS PeriodYear,
        mo.M AS PeriodMonth,
        ISNULL(r.Revenue, 0) AS Revenue,
        ISNULL(e.Expense, 0) AS Expense,
        ISNULL(r.Revenue, 0) - ISNULL(e.Expense, 0) AS Profit,
        ISNULL(col.Collected, 0) AS Collected,
        ISNULL(r.Revenue, 0) - ISNULL(col.Collected, 0) AS Outstanding
    FROM dbo.BusinessSegments s
    CROSS JOIN Months mo
    LEFT JOIN dbo.vw_SegmentMonthlyRevenue r
        ON r.BusinessSegmentId = s.BusinessSegmentId AND r.PeriodYear = mo.Y AND r.PeriodMonth = mo.M
    LEFT JOIN dbo.vw_SegmentMonthlyExpense e
        ON e.BusinessSegmentId = s.BusinessSegmentId AND e.PeriodYear = mo.Y AND e.PeriodMonth = mo.M
    LEFT JOIN (
        SELECT a.BusinessSegmentId, YEAR(r2.ReceiptDate) AS Y, MONTH(r2.ReceiptDate) AS M,
               SUM(a.AllocatedAmount) AS Collected
        FROM dbo.ReceiptInvoiceAllocations a
        INNER JOIN dbo.Receipts r2 ON r2.ReceiptId = a.ReceiptId
        GROUP BY a.BusinessSegmentId, YEAR(r2.ReceiptDate), MONTH(r2.ReceiptDate)
    ) col ON col.BusinessSegmentId = s.BusinessSegmentId AND col.Y = mo.Y AND col.M = mo.M
    WHERE s.IsActive = 1
    ORDER BY mo.Y, mo.M, s.SortOrder;
END
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
        SELECT l.TxnDate, l.VoucherNo, l.Particulars, l.Debit, l.Credit, l.SortOrder
        FROM dbo.vw_ClientLedger l
        WHERE l.ClientId = @ClientId
          AND l.TxnDate BETWEEN @FromDate AND @ToDate
          AND (@BusinessSegmentId IS NULL OR l.SortOrder = 0
               OR EXISTS (
                   SELECT 1 FROM dbo.TaxInvoices ti
                   WHERE ti.InvoiceNumber = l.VoucherNo AND ti.BusinessSegmentId = @BusinessSegmentId
               )
               OR EXISTS (
                   SELECT 1 FROM dbo.Receipts r
                   INNER JOIN dbo.ReceiptInvoiceAllocations ria ON ria.ReceiptId = r.ReceiptId
                   WHERE r.ReceiptNumber = l.VoucherNo AND ria.BusinessSegmentId = @BusinessSegmentId
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

CREATE OR ALTER PROCEDURE dbo.sp_GetExecutiveCharts
AS
BEGIN
    SET NOCOUNT ON;
    -- Monthly revenue
    SELECT YEAR(InvoiceDate) AS Y, MONTH(InvoiceDate) AS M,
           SUM(TotalAmount) AS Amount, N'revenue' AS ChartType
    FROM dbo.TaxInvoices
    WHERE InvoiceDate >= DATEADD(MONTH, -11, CAST(GETDATE() AS DATE))
    GROUP BY YEAR(InvoiceDate), MONTH(InvoiceDate)
    ORDER BY Y, M;

    -- Monthly collections
    SELECT YEAR(ReceiptDate) AS Y, MONTH(ReceiptDate) AS M,
           SUM(AmountReceived) AS Amount, N'collections' AS ChartType
    FROM dbo.Receipts
    WHERE ReceiptDate >= DATEADD(MONTH, -11, CAST(GETDATE() AS DATE))
    GROUP BY YEAR(ReceiptDate), MONTH(ReceiptDate)
    ORDER BY Y, M;

    -- Top clients by revenue
    SELECT TOP 10 c.ClientName, SUM(i.TotalAmount) AS Amount
    FROM dbo.TaxInvoices i
    INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
    GROUP BY c.ClientName
    ORDER BY Amount DESC;

    -- Top outstanding
    SELECT TOP 10 ClientName, Outstanding AS Amount
    FROM dbo.vw_ClientOutstanding
    WHERE Outstanding > 0
    ORDER BY Outstanding DESC;

    -- Segment revenue trend
    SELECT BusinessSegmentId, BusinessSegmentName, PeriodYear AS Y, PeriodMonth AS M, Revenue AS Amount
    FROM dbo.vw_SegmentMonthlyRevenue
    WHERE DATEFROMPARTS(PeriodYear, PeriodMonth, 1) >= DATEADD(MONTH, -11, CAST(GETDATE() AS DATE))
    ORDER BY Y, M, BusinessSegmentId;

    -- Segment expense trend
    SELECT BusinessSegmentId, BusinessSegmentName, PeriodYear AS Y, PeriodMonth AS M, Expense AS Amount
    FROM dbo.vw_SegmentMonthlyExpense
    WHERE DATEFROMPARTS(PeriodYear, PeriodMonth, 1) >= DATEADD(MONTH, -11, CAST(GETDATE() AS DATE))
    ORDER BY Y, M, BusinessSegmentId;
END
GO
