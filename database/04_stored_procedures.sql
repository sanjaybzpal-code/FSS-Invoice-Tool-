-- FSS Invoice & Accounts — stored procedures
USE FSSInvoice;
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetClientLedger
    @ClientId INT,
    @FromDate DATE = NULL,
    @ToDate   DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @FromDate IS NULL SET @FromDate = '1900-01-01';
    IF @ToDate IS NULL SET @ToDate = '9999-12-31';

    ;WITH Ledger AS (
        SELECT TxnDate, VoucherNo, Particulars, Debit, Credit, SortOrder
        FROM dbo.vw_ClientLedger
        WHERE ClientId = @ClientId
          AND TxnDate BETWEEN @FromDate AND @ToDate
    ),
    Running AS (
        SELECT
            TxnDate, VoucherNo, Particulars, Debit, Credit,
            SUM(Debit - Credit) OVER (ORDER BY TxnDate, SortOrder, VoucherNo
                ROWS UNBOUNDED PRECEDING) AS RunningBalance
        FROM Ledger
    )
    SELECT TxnDate AS [Date], VoucherNo, Particulars, Debit, Credit, RunningBalance
    FROM Running
    ORDER BY TxnDate, VoucherNo;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetOutstandingDashboard
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.vw_OutstandingDashboard;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetAgeingAnalysis
AS
BEGIN
    SET NOCOUNT ON;
    SELECT AgeBucket,
           COUNT(*) AS InvoiceCount,
           SUM(PendingAmount) AS PendingAmount
    FROM dbo.vw_InvoiceAgeing
    GROUP BY AgeBucket
    ORDER BY CASE AgeBucket
        WHEN N'0-30 Days' THEN 1
        WHEN N'31-60 Days' THEN 2
        WHEN N'61-90 Days' THEN 3
        ELSE 4 END;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_GetClientSummary
    @ClientId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.vw_ClientOutstanding WHERE ClientId = @ClientId;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_NextReceiptNumber
    @NextNumber NVARCHAR(30) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @n INT;
    UPDATE dbo.LedgerSequence WITH (ROWLOCK)
    SET @n = NextValue, NextValue = NextValue + 1
    WHERE SeqName = N'RECEIPT';
    SET @NextNumber = N'RCP-' + RIGHT(N'00000' + CAST(@n AS NVARCHAR), 5);
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_UpsertClient
    @ClientName NVARCHAR(200),
    @GSTIN NVARCHAR(20) = NULL,
    @Address NVARCHAR(500) = NULL,
    @ContactPerson NVARCHAR(100) = NULL,
    @Email NVARCHAR(150) = NULL,
    @Mobile NVARCHAR(20) = NULL,
    @MhState BIT = 0,
    @ClientId INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT @ClientId = ClientId FROM dbo.ClientMaster WHERE ClientName = @ClientName;
    IF @ClientId IS NULL
    BEGIN
        INSERT INTO dbo.ClientMaster (ClientName, GSTIN, Address, ContactPerson, Email, Mobile, MhState)
        VALUES (@ClientName, @GSTIN, @Address, @ContactPerson, @Email, @Mobile, @MhState);
        SET @ClientId = SCOPE_IDENTITY();
    END
    ELSE
    BEGIN
        UPDATE dbo.ClientMaster SET
            GSTIN = COALESCE(@GSTIN, GSTIN),
            Address = COALESCE(@Address, Address),
            ContactPerson = COALESCE(@ContactPerson, ContactPerson),
            Email = COALESCE(@Email, Email),
            Mobile = COALESCE(@Mobile, Mobile),
            MhState = @MhState,
            UpdatedAt = SYSUTCDATETIME()
        WHERE ClientId = @ClientId;
    END
END
GO
