-- AR views: reminders, GST, executive, profitability
USE FSSInvoice;
GO

CREATE OR ALTER VIEW dbo.vw_InvoiceOutstanding AS
SELECT
    i.InvoiceId, i.ClientId, c.ClientName, c.Email, c.Mobile,
    i.InvoiceNumber, i.InvoiceDate, i.DueDate,
    i.TaxableAmount, i.CGSTAmount, i.SGSTAmount, i.IGSTAmount, i.TotalAmount,
    ISNULL(p.Paid, 0) AS PaidAmount,
    i.TotalAmount - ISNULL(p.Paid, 0) AS OutstandingAmount,
    DATEDIFF(DAY, i.DueDate, CAST(GETDATE() AS DATE)) AS DaysFromDue
FROM dbo.TaxInvoices i
INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
LEFT JOIN (
    SELECT InvoiceId, SUM(AmountReceived + TdsAmount) AS Paid
    FROM dbo.Receipts r
    INNER JOIN dbo.TaxInvoices ti ON ti.ClientId = r.ClientId
    GROUP BY ti.InvoiceId
) p ON 1=0  -- simplified: use ageing view for pending
;
GO

-- Pending per invoice (FIFO allocation from client receipts)
CREATE OR ALTER VIEW dbo.vw_InvoicePending AS
SELECT a.*
FROM dbo.vw_InvoiceAgeing a;
GO

CREATE OR ALTER VIEW dbo.vw_ReminderDashboard AS
SELECT
    SUM(CASE WHEN DaysFromDue = 0 AND OutstandingAmount > 0 THEN 1 ELSE 0 END) AS DueToday,
    SUM(CASE WHEN DaysFromDue BETWEEN -7 AND -1 AND OutstandingAmount > 0 THEN 1 ELSE 0 END) AS DueThisWeek,
    SUM(CASE WHEN DaysFromDue BETWEEN 1 AND 30 AND OutstandingAmount > 0 THEN 1 ELSE 0 END) AS Overdue,
    SUM(CASE WHEN DaysFromDue > 30 AND OutstandingAmount > 0 THEN 1 ELSE 0 END) AS CriticalOverdue
FROM (
    SELECT i.InvoiceId,
           DATEDIFF(DAY, ISNULL(i.DueDate, DATEADD(DAY,30,i.InvoiceDate)), CAST(GETDATE() AS DATE)) AS DaysFromDue,
           ia.PendingAmount AS OutstandingAmount
    FROM dbo.TaxInvoices i
    INNER JOIN dbo.vw_InvoiceAgeing ia ON ia.InvoiceId = i.InvoiceId
) x;
GO

CREATE OR ALTER VIEW dbo.vw_GstReceivable AS
SELECT
    i.InvoiceId, i.ClientId, c.ClientName,
    i.InvoiceNumber, i.InvoiceDate,
    YEAR(i.InvoiceDate) AS InvYear,
    MONTH(i.InvoiceDate) AS InvMonth,
    DATEPART(QUARTER, i.InvoiceDate) AS InvQuarter,
    i.TaxableAmount,
    i.CGSTAmount, i.SGSTAmount, i.IGSTAmount,
    (i.CGSTAmount + i.SGSTAmount + i.IGSTAmount) AS TotalGst,
    ia.PendingAmount,
    CASE WHEN ia.PendingAmount > 0 THEN ia.PendingAmount * i.CGSTAmount / NULLIF(i.TotalAmount,0) ELSE 0 END AS CgstOutstanding,
    CASE WHEN ia.PendingAmount > 0 THEN ia.PendingAmount * i.SGSTAmount / NULLIF(i.TotalAmount,0) ELSE 0 END AS SgstOutstanding,
    CASE WHEN ia.PendingAmount > 0 THEN ia.PendingAmount * i.IGSTAmount / NULLIF(i.TotalAmount,0) ELSE 0 END AS IgstOutstanding
FROM dbo.TaxInvoices i
INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
LEFT JOIN dbo.vw_InvoiceAgeing ia ON ia.InvoiceId = i.InvoiceId;
GO

CREATE OR ALTER VIEW dbo.vw_GstReceivableSummary AS
SELECT
    SUM(TaxableAmount) AS TotalTaxable,
    SUM(CGSTAmount) AS TotalCgst,
    SUM(SGSTAmount) AS TotalSgst,
    SUM(IGSTAmount) AS TotalIgst,
    SUM(TotalGst) AS TotalGstInvoiced,
    SUM(CgstOutstanding + SgstOutstanding + IgstOutstanding) AS TotalGstOutstanding
FROM dbo.vw_GstReceivable;
GO

CREATE OR ALTER VIEW dbo.vw_ClientProfitability AS
SELECT
    pc.ClientId, c.ClientName, pc.ProjectName,
    pc.PeriodYear, pc.PeriodMonth,
    pc.Revenue, pc.ConsultancyCharges, pc.Manhours,
    pc.EmployeeCost, pc.TravelCost, pc.MiscellaneousCost,
    (pc.EmployeeCost + pc.TravelCost + pc.MiscellaneousCost + pc.ConsultancyCharges) AS TotalCost,
    pc.Revenue - (pc.EmployeeCost + pc.TravelCost + pc.MiscellaneousCost + pc.ConsultancyCharges) AS GrossProfit,
    CASE WHEN pc.Revenue > 0
         THEN 100.0 * (pc.Revenue - (pc.EmployeeCost + pc.TravelCost + pc.MiscellaneousCost + pc.ConsultancyCharges)) / pc.Revenue
         ELSE 0 END AS ProfitPercent,
    CASE WHEN pc.Manhours > 0 THEN pc.Revenue / pc.Manhours ELSE 0 END AS RevenuePerManhour
FROM dbo.ProjectCosts pc
INNER JOIN dbo.ClientMaster c ON c.ClientId = pc.ClientId;
GO

CREATE OR ALTER VIEW dbo.vw_ExecutiveDashboard AS
SELECT
    (SELECT ISNULL(SUM(TotalAmount),0) FROM dbo.TaxInvoices) AS TotalInvoiced,
    (SELECT ISNULL(SUM(AmountReceived),0) FROM dbo.Receipts) AS TotalReceived,
    (SELECT ISNULL(SUM(Outstanding),0) FROM dbo.vw_ClientOutstanding) AS TotalOutstanding,
    (SELECT ISNULL(TotalGstOutstanding,0) FROM dbo.vw_GstReceivableSummary) AS TotalGstReceivable,
    (SELECT ISNULL(SUM(TdsAmount),0) FROM dbo.Receipts) AS TotalTdsDeducted,
    (SELECT COUNT(*) FROM dbo.ClientMaster WHERE IsActive=1) AS TotalActiveClients;
GO

CREATE OR ALTER VIEW dbo.vw_TdsSummary AS
SELECT
    r.ClientId, c.ClientName, r.FinancialYear,
    SUM(r.TdsAmount) AS TotalTds,
    SUM(CASE WHEN r.TdsCertificateReceived = 1 THEN r.TdsAmount ELSE 0 END) AS TdsCertified,
    SUM(CASE WHEN r.TdsCertificateReceived = 0 AND r.TdsAmount > 0 THEN r.TdsAmount ELSE 0 END) AS TdsPendingCert
FROM dbo.Receipts r
INNER JOIN dbo.ClientMaster c ON c.ClientId = r.ClientId
WHERE r.TdsAmount > 0
GROUP BY r.ClientId, c.ClientName, r.FinancialYear;
GO
