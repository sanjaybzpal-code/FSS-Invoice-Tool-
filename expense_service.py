"""Expense management and segment allocation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import db
import segment_service as seg_svc


def _rows(cur) -> list[dict]:
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _row(cur) -> dict | None:
    r = _rows(cur)
    return r[0] if r else None


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


# --- Categories --------------------------------------------------------------
def list_categories(active_only: bool = True) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        sql = "SELECT * FROM dbo.ExpenseCategories"
        if active_only:
            sql += " WHERE IsActive = 1"
        sql += " ORDER BY CategoryName"
        cur.execute(sql)
        return _rows(cur)


def add_category(name: str) -> int:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dbo.ExpenseCategories (CategoryName, IsSystem)
               OUTPUT INSERTED.ExpenseCategoryId VALUES (?, 0)""",
            name.strip())
        cid = int(cur.fetchone()[0])
        conn.commit()
        return cid


# --- Revenue shares for common expense allocation ----------------------------
def _revenue_shares() -> dict[int, float]:
    rows = seg_svc.segment_dashboard()
    total = sum(float(r.get("TotalRevenue") or 0) for r in rows)
    if total <= 0:
        n = max(len(rows), 1)
        return {r["BusinessSegmentId"]: 1.0 / n for r in rows}
    return {r["BusinessSegmentId"]: float(r.get("TotalRevenue") or 0) / total for r in rows}


def _save_allocations(cur, expense_id: int, allocs: list[tuple[int, float, float | None]]) -> None:
    cur.execute("DELETE FROM dbo.ExpenseSegmentAllocations WHERE ExpenseId = ?", expense_id)
    for seg_id, amt, pct in allocs:
        cur.execute(
            """INSERT INTO dbo.ExpenseSegmentAllocations
               (ExpenseId, BusinessSegmentId, AllocatedAmount, AllocPercent)
               VALUES (?,?,?,?)""",
            expense_id, seg_id, round(amt, 2), pct)


def _compute_common_allocations(total: float, method: str,
                                manual: dict[int, float] | None = None) -> list[tuple[int, float, float | None]]:
    segments = seg_svc.list_segments()
    allocs: list[tuple[int, float, float | None]] = []
    if method == "common_equal":
        share = total / max(len(segments), 1)
        for s in segments:
            allocs.append((s["BusinessSegmentId"], share, 100.0 / max(len(segments), 1)))
    elif method == "common_revenue":
        shares = _revenue_shares()
        for s in segments:
            sid = s["BusinessSegmentId"]
            pct = shares.get(sid, 0) * 100
            allocs.append((sid, total * shares.get(sid, 0), pct))
    elif method == "common_manual" and manual:
        for sid, pct in manual.items():
            allocs.append((int(sid), total * float(pct) / 100.0, float(pct)))
    else:
        share = total / max(len(segments), 1)
        for s in segments:
            allocs.append((s["BusinessSegmentId"], share, 100.0 / max(len(segments), 1)))
    return allocs


# --- Expense CRUD ------------------------------------------------------------
def list_expenses(limit: int = 500, year: int | None = None, month: int | None = None) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        sql = """SELECT TOP (?) e.*, ec.CategoryName, bs.BusinessSegmentName
                 FROM dbo.Expenses e
                 INNER JOIN dbo.ExpenseCategories ec ON ec.ExpenseCategoryId = e.ExpenseCategoryId
                 LEFT JOIN dbo.BusinessSegments bs ON bs.BusinessSegmentId = e.BusinessSegmentId
                 WHERE 1=1"""
        params: list[Any] = [limit]
        if year:
            sql += " AND YEAR(e.ExpenseDate) = ?"
            params.append(year)
        if month:
            sql += " AND MONTH(e.ExpenseDate) = ?"
            params.append(month)
        sql += " ORDER BY e.ExpenseDate DESC, e.ExpenseId DESC"
        cur.execute(sql, *params)
        return _rows(cur)


def get_expense(expense_id: int) -> dict | None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT e.*, ec.CategoryName FROM dbo.Expenses e
               INNER JOIN dbo.ExpenseCategories ec ON ec.ExpenseCategoryId = e.ExpenseCategoryId
               WHERE e.ExpenseId = ?""", expense_id)
        exp = _row(cur)
        if not exp:
            return None
        cur.execute(
            """SELECT esa.*, bs.BusinessSegmentName FROM dbo.ExpenseSegmentAllocations esa
               INNER JOIN dbo.BusinessSegments bs ON bs.BusinessSegmentId = esa.BusinessSegmentId
               WHERE esa.ExpenseId = ?""", expense_id)
        exp["allocations"] = _rows(cur)
        return exp


def save_expense(data: dict, user: str = "") -> int:
    edate = _parse_date(data.get("expense_date")) or date.today()
    cat_id = int(data["category_id"])
    desc = (data.get("description") or "").strip()
    amount = float(data.get("amount") or 0)
    gst = float(data.get("gst_amount") or 0)
    total = amount + gst
    alloc_type = data.get("allocation_type") or "segment"
    seg_id = int(data["segment_id"]) if data.get("segment_id") and alloc_type == "segment" else None

    expense_id = data.get("expense_id")
    with db.get_connection() as conn:
        cur = conn.cursor()
        if expense_id:
            cur.execute(
                """UPDATE dbo.Expenses SET ExpenseDate=?, ExpenseCategoryId=?, ExpenseDescription=?,
                   Amount=?, GstAmount=?, VendorName=?, PaymentMode=?, ReferenceNumber=?,
                   Remarks=?, AllocationType=?, BusinessSegmentId=?, UpdatedAt=SYSUTCDATETIME()
                   WHERE ExpenseId=?""",
                edate, cat_id, desc, amount, gst,
                data.get("vendor") or None, data.get("payment_mode") or None,
                data.get("reference") or None, data.get("remarks") or None,
                alloc_type, seg_id, int(expense_id))
            eid = int(expense_id)
        else:
            cur.execute(
                """INSERT INTO dbo.Expenses
                   (ExpenseDate, ExpenseCategoryId, ExpenseDescription, Amount, GstAmount,
                    VendorName, PaymentMode, ReferenceNumber, Remarks, AllocationType,
                    BusinessSegmentId, CreatedBy)
                   OUTPUT INSERTED.ExpenseId VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                edate, cat_id, desc, amount, gst,
                data.get("vendor") or None, data.get("payment_mode") or None,
                data.get("reference") or None, data.get("remarks") or None,
                alloc_type, seg_id, user or None)
            eid = int(cur.fetchone()[0])

        if alloc_type == "segment":
            cur.execute("DELETE FROM dbo.ExpenseSegmentAllocations WHERE ExpenseId = ?", eid)
        else:
            manual = data.get("manual_alloc") or {}
            allocs = _compute_common_allocations(total, alloc_type, manual)
            _save_allocations(cur, eid, allocs)
        conn.commit()
        return eid


def delete_expense(expense_id: int) -> None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM dbo.Expenses WHERE ExpenseId = ?", expense_id)
        conn.commit()


def month_expense_total(year: int, month: int) -> float:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT ISNULL(SUM(TotalAmount),0) FROM dbo.Expenses
               WHERE YEAR(ExpenseDate)=? AND MONTH(ExpenseDate)=?""",
            year, month)
        return float(cur.fetchone()[0])
