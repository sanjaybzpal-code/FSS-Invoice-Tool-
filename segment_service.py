"""Business segment reporting and filters."""

from __future__ import annotations

from typing import Any

import db


def _rows(cur) -> list[dict]:
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _row(cur) -> dict | None:
    r = _rows(cur)
    return r[0] if r else None


def list_segments(active_only: bool = True) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        sql = "SELECT * FROM dbo.BusinessSegments"
        if active_only:
            sql += " WHERE IsActive = 1"
        sql += " ORDER BY SortOrder, BusinessSegmentName"
        cur.execute(sql)
        return _rows(cur)


def get_segment(segment_id: int) -> dict | None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dbo.BusinessSegments WHERE BusinessSegmentId = ?", segment_id)
        return _row(cur)


def segment_by_name(name: str) -> dict | None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM dbo.BusinessSegments WHERE BusinessSegmentName = ?", name)
        return _row(cur)


def segment_dashboard(segment_id: int | None = None) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetSegmentDashboard")
        rows = _rows(cur)
    if segment_id:
        rows = [r for r in rows if r["BusinessSegmentId"] == segment_id]
    return rows


def segment_profitability(segment_id: int | None = None) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetSegmentProfitability")
        rows = _rows(cur)
    if segment_id:
        rows = [r for r in rows if r["BusinessSegmentId"] == segment_id]
    return rows


def segment_monthly_trend(months: int = 12, segment_id: int | None = None) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetSegmentMonthlyTrend ?", months)
        rows = _rows(cur)
    if segment_id:
        rows = [r for r in rows if r["BusinessSegmentId"] == segment_id]
    return rows


def executive_segment_cards() -> dict[str, Any]:
    """Cards for executive summary: revenue/outstanding per segment."""
    rows = segment_dashboard()
    cards = {"segments": rows}
    for r in rows:
        sid = r["BusinessSegmentId"]
        code = (r.get("BusinessSegmentName") or "").replace(" ", "")
        cards[f"revenue_{sid}"] = float(r.get("TotalRevenue") or 0)
        cards[f"outstanding_{sid}"] = float(r.get("Outstanding") or 0)
    cards["total_revenue"] = sum(float(r.get("TotalRevenue") or 0) for r in rows)
    cards["total_outstanding"] = sum(float(r.get("Outstanding") or 0) for r in rows)
    return cards


def mis_report(year: int, month: int, segment_id: int | None = None) -> dict:
    with db.get_connection() as conn:
        cur = conn.cursor()
        # Segment P&L for month
        cur.execute("EXEC dbo.sp_GetSegmentProfitability")
        pl = _rows(cur)
        if segment_id:
            pl = [r for r in pl if r["BusinessSegmentId"] == segment_id]

        cur.execute(
            """SELECT TOP 10 c.ClientName, SUM(i.TotalAmount) AS Revenue
               FROM dbo.TaxInvoices i
               INNER JOIN dbo.ClientMaster c ON c.ClientId = i.ClientId
               WHERE YEAR(i.InvoiceDate)=? AND MONTH(i.InvoiceDate)=?
               """ + (" AND i.BusinessSegmentId=?" if segment_id else "") + """
               GROUP BY c.ClientName ORDER BY Revenue DESC""",
            (year, month, segment_id) if segment_id else (year, month))
        top_clients = _rows(cur)

        cur.execute(
            """SELECT TOP 10 ec.CategoryName, SUM(ea.AllocatedAmount) AS Expense
               FROM dbo.vw_SegmentExpenseAllocated ea
               INNER JOIN dbo.ExpenseCategories ec ON ec.ExpenseCategoryId = ea.ExpenseCategoryId
               WHERE YEAR(ea.ExpenseDate)=? AND MONTH(ea.ExpenseDate)=?
               """ + (" AND ea.BusinessSegmentId=?" if segment_id else "") + """
               GROUP BY ec.CategoryName ORDER BY Expense DESC""",
            (year, month, segment_id) if segment_id else (year, month))
        top_expenses = _rows(cur)

        cur.execute(
            """SELECT SUM(i.TotalAmount) AS Revenue,
                      SUM(CASE WHEN ria.AllocatedAmount IS NOT NULL THEN ria.AllocatedAmount ELSE 0 END) AS Collected
               FROM dbo.TaxInvoices i
               LEFT JOIN dbo.ReceiptInvoiceAllocations ria ON ria.InvoiceId = i.InvoiceId
               WHERE YEAR(i.InvoiceDate)=? AND MONTH(i.InvoiceDate)=?
               """ + (" AND i.BusinessSegmentId=?" if segment_id else ""),
            (year, month, segment_id) if segment_id else (year, month))
        month_rev = _row(cur) or {}

    seg_rows = segment_dashboard(segment_id)
    return {
        "year": year, "month": month,
        "profitability": pl,
        "top_clients": top_clients,
        "top_expenses": top_expenses,
        "month_revenue": float(month_rev.get("Revenue") or 0),
        "month_collected": float(month_rev.get("Collected") or 0),
        "segments": seg_rows,
    }
