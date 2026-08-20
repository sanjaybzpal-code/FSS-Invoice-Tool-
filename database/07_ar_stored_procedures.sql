-- AR stored procedures
USE FSSInvoice;
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetReminderDashboard
AS
BEGIN
    SET NOCOUNT ON;
    ;WITH P AS (
        SELECT i.InvoiceId, i.DueDate, i.InvoiceDate, ia.PendingAmount,
               ISNULL(i.DueDate, DATEADD(DAY, ISNULL(i.PaymentTermsDays,30), i.InvoiceDate)) AS EffDue
        FROM dbo.TaxInvoices i
        INNER JOIN dbo.vw_InvoiceAgeing ia ON ia.InvoiceId = i.InvoiceId
        WHERE ia.PendingAmount > 0.01
    )
    SELECT
        SUM(CASE WHEN EffDue = CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END) AS DueToday,
        SUM(CASE WHEN EffDue > CAST(GETDATE() AS DATE)
                  AND EffDue <= DATEADD(DAY, 7, CAST(GETDATE() AS DATE)) THEN 1 ELSE 0 END) AS DueThisWeek,
        SUM(CASE WHEN EffDue < CAST(GETDATE() AS DATE)
                  AND DATEDIFF(DAY, EffDue, CAST(GETDATE() AS DATE)) <= 30 THEN 1 ELSE 0 END) AS Overdue,
        SUM(CASE WHEN EffDue < CAST(GETDATE() AS DATE)
                  AND DATEDIFF(DAY, EffDue, CAST(GETDATE() AS DATE)) > 30 THEN 1 ELSE 0 END) AS CriticalOverdue
    FROM P;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetRemindersDue
    @RuleType NVARCHAR(30) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    ;WITH P AS (
        SELECT i.InvoiceId, i.ClientId, c.ClientName, c.Email, c.Mobile,
               i.InvoiceNumber, i.InvoiceDate,
               ISNULL(i.DueDate, DATEADD(DAY, ISNULL(i.PaymentTermsDays,30), i.InvoiceDate)) AS EffDue,
               ia.PendingAmount AS OutstandingAmount, i.PdfPath,
               DATEDIFF(DAY, CAST(GETDATE() AS DATE),
                   ISNULL(i.DueDate, DATEADD(DAY, ISNULL(i.PaymentTermsDays,30), i.InvoiceDate))) AS DaysToDue
        FROM dbo.TaxInvoices i
        INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
        INNER JOIN dbo.vw_InvoiceAgeing ia ON ia.InvoiceId = i.InvoiceId
        WHERE ia.PendingAmount > 0.01
    )
    SELECT *, CASE
        WHEN DaysToDue = 7 THEN N'before_7'
        WHEN DaysToDue = 0 THEN N'on_due'
        WHEN DaysToDue = -7 THEN N'after_7'
        WHEN DaysToDue = -15 THEN N'after_15'
        WHEN DaysToDue = -30 THEN N'after_30'
        ELSE NULL END AS SuggestedRule
    FROM P
    WHERE (@RuleType IS NULL AND DaysToDue IN (7,0,-7,-15,-30))
       OR (@RuleType = N'before_7' AND DaysToDue = 7)
       OR (@RuleType = N'on_due' AND DaysToDue = 0)
       OR (@RuleType = N'after_7' AND DaysToDue = -7)
       OR (@RuleType = N'after_15' AND DaysToDue = -15)
       OR (@RuleType = N'after_30' AND DaysToDue = -30);
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetExecutiveCharts
AS
BEGIN
    SET NOCOUNT ON;
    -- Monthly revenue
    SELECT YEAR(InvoiceDate) AS Yr, MONTH(InvoiceDate) AS Mo,
           SUM(TotalAmount) AS Revenue
    FROM dbo.TaxInvoices
    GROUP BY YEAR(InvoiceDate), MONTH(InvoiceDate)
    ORDER BY Yr, Mo;

    -- Monthly collections
    SELECT YEAR(ReceiptDate) AS Yr, MONTH(ReceiptDate) AS Mo,
           SUM(AmountReceived) AS Collections
    FROM dbo.Receipts
    GROUP BY YEAR(ReceiptDate), MONTH(ReceiptDate)
    ORDER BY Yr, Mo;

    -- Top clients by revenue
    SELECT TOP 10 c.ClientName, SUM(i.TotalAmount) AS Revenue
    FROM dbo.TaxInvoices i INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
    GROUP BY c.ClientName ORDER BY Revenue DESC;

    -- Top outstanding
    SELECT TOP 10 ClientName, Outstanding
    FROM dbo.vw_ClientOutstanding WHERE Outstanding > 0
    ORDER BY Outstanding DESC;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetGstMonthWise
    @Year INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @Year IS NULL SET @Year = YEAR(GETDATE());
    SELECT InvMonth AS [Month],
           SUM(TaxableAmount) AS Taxable,
           SUM(CGSTAmount) AS CGST, SUM(SGSTAmount) AS SGST, SUM(IGSTAmount) AS IGST,
           SUM(CgstOutstanding + SgstOutstanding + IgstOutstanding) AS GstOutstanding
    FROM dbo.vw_GstReceivable WHERE InvYear = @Year
    GROUP BY InvMonth ORDER BY InvMonth;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetGstClientWise
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ClientName,
           SUM(TaxableAmount) AS Taxable,
           SUM(CGSTAmount) AS CGST, SUM(SGSTAmount) AS SGST, SUM(IGSTAmount) AS IGST,
           SUM(CgstOutstanding + SgstOutstanding + IgstOutstanding) AS GstOutstanding
    FROM dbo.vw_GstReceivable
    GROUP BY ClientName ORDER BY GstOutstanding DESC;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_LogAudit
    @UserName NVARCHAR(50), @Action NVARCHAR(100),
    @EntityType NVARCHAR(50) = NULL, @EntityId NVARCHAR(50) = NULL,
    @Details NVARCHAR(MAX) = NULL, @IpAddress NVARCHAR(50) = NULL
AS
BEGIN
    INSERT INTO dbo.AuditLog (UserName, Action, EntityType, EntityId, Details, IpAddress)
    VALUES (@UserName, @Action, @EntityType, @EntityId, @Details, @IpAddress);
END
GO
