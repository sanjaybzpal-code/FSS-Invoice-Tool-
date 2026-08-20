"""Accounts Receivable services: reminders, WhatsApp, TDS, GST, profitability, executive."""

from __future__ import annotations

import json
import os
import re
import smtplib
import urllib.parse
from datetime import date, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import db

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

REMINDER_RULES = {
    "before_7": 7,    # 7 days before due
    "on_due": 0,
    "after_7": -7,
    "after_15": -15,
    "after_30": -30,
}


def _rows(cur) -> list[dict]:
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _row(cur) -> dict | None:
    r = _rows(cur)
    return r[0] if r else None


def _config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _financial_year(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.year}-{d.year + 1}" if d.month >= 4 else f"{d.year - 1}-{d.year}"


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


# --- Reminders ---------------------------------------------------------------
def reminder_dashboard() -> dict:
    if db.use_snapshot_fallback():
        import vercel_snapshot as vs
        return vs.reminder_dashboard()
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetReminderDashboard")
        return _row(cur) or {}


def reminder_history(limit: int = 100) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT TOP (?) rh.*, i.InvoiceNumber, c.ClientName
               FROM dbo.ReminderHistory rh
               INNER JOIN dbo.TaxInvoices i ON i.InvoiceId = rh.InvoiceId
               INNER JOIN dbo.ClientMaster c ON c.ClientId = rh.ClientId
               ORDER BY rh.SentAt DESC""", limit)
        return _rows(cur)


def _already_sent(invoice_id: int, rule: str, channel: str) -> bool:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT 1 FROM dbo.ReminderHistory
               WHERE InvoiceId=? AND RuleType=? AND Channel=?""",
            invoice_id, rule, channel)
        return cur.fetchone() is not None


def _record_reminder(invoice_id, client_id, rule, channel, recipient, status, body, user):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dbo.ReminderHistory
               (InvoiceId,ClientId,RuleType,Channel,Recipient,DeliveryStatus,MessageBody,CreatedBy)
               VALUES (?,?,?,?,?,?,?,?)""",
            invoice_id, client_id, rule, channel, recipient, status, body, user)
        conn.commit()


def send_email_reminder(invoice_row: dict, rule: str, user: str = "") -> tuple[bool, str]:
    cfg = _config()
    em = cfg.get("email", {})
    to_addr = (invoice_row.get("Email") or "").strip()
    if not to_addr:
        return False, "No email on file for client."
    if _already_sent(invoice_row["InvoiceId"], rule, "email"):
        return False, "Reminder already sent for this rule."

    due = invoice_row.get("EffDue") or invoice_row.get("DueDate")
    due_s = due.strftime("%d-%m-%Y") if hasattr(due, "strftime") else str(due)
    inv_date = invoice_row.get("InvoiceDate")
    inv_s = inv_date.strftime("%d-%m-%Y") if hasattr(inv_date, "strftime") else str(inv_date)
    amt = float(invoice_row.get("OutstandingAmount") or 0)

    subject = f"Payment Reminder — Invoice {invoice_row['InvoiceNumber']} — Façade Structural Services"
    body = f"""Dear {invoice_row.get('ClientName', 'Sir/Madam')},

This is a friendly reminder regarding the following tax invoice:

  Invoice Number  : {invoice_row['InvoiceNumber']}
  Invoice Date    : {inv_s}
  Due Date        : {due_s}
  Outstanding Amt : ₹ {amt:,.2f}

Kindly arrange payment at the earliest. For queries, reply to this email.

Regards,
{cfg.get('seller', {}).get('name', 'Façade Structural Services')}
{cfg.get('seller', {}).get('email', '')}
"""
    msg = MIMEMultipart()
    msg["From"] = em.get("from_address", cfg["seller"]["email"])
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    pdf_path = invoice_row.get("PdfPath") or ""
    if pdf_path and os.path.isfile(pdf_path):
        with open(pdf_path, "rb") as fh:
            part = MIMEApplication(fh.read(), Name=os.path.basename(pdf_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)

    host = em.get("smtp_host", "")
    if not host:
        _record_reminder(invoice_row["InvoiceId"], invoice_row["ClientId"],
                         rule, "email", to_addr, "skipped_no_smtp", body, user)
        return False, "SMTP not configured in config.json → email section."

    try:
        port = int(em.get("smtp_port", 587))
        with smtplib.SMTP(host, port, timeout=30) as server:
            if em.get("use_tls", True):
                server.starttls()
            user_smtp = em.get("smtp_user", "")
            if user_smtp:
                server.login(user_smtp, em.get("smtp_password", ""))
            server.send_message(msg)
        _record_reminder(invoice_row["InvoiceId"], invoice_row["ClientId"],
                         rule, "email", to_addr, "sent", body, user)
        return True, f"Email sent to {to_addr}"
    except Exception as exc:  # noqa: BLE001
        _record_reminder(invoice_row["InvoiceId"], invoice_row["ClientId"],
                         rule, "email", to_addr, f"failed: {exc}", body, user)
        return False, str(exc)


def process_automatic_reminders(user: str = "system") -> list[str]:
    results = []
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetRemindersDue")
        rows = _rows(cur)
    for row in rows:
        rule = row.get("SuggestedRule")
        if not rule:
            continue
        ok, msg = send_email_reminder(row, rule, user)
        results.append(f"{row['InvoiceNumber']} ({rule}): {msg}")
    return results


# --- WhatsApp ----------------------------------------------------------------
def _clean_mobile(mobile: str) -> str:
    digits = re.sub(r"\D", "", mobile or "")
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def whatsapp_message(client_name: str, invoice_no: str, amount: float) -> str:
    return (
        f"Dear {client_name},\n\n"
        f"This is a reminder that Invoice {invoice_no} amounting to "
        f"₹{amount:,.2f} remains outstanding.\n\n"
        f"Kindly arrange payment at the earliest.\n\n"
        f"Regards,\nFacade Structural Services"
    )


def whatsapp_link(mobile: str, text: str) -> str:
    return f"https://wa.me/{_clean_mobile(mobile)}?text={urllib.parse.quote(text)}"


def log_whatsapp(client_id: int, mobile: str, msg_type: str, body: str,
                 user: str, invoice_id: int | None = None) -> None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dbo.WhatsAppLog
               (ClientId, InvoiceId, Mobile, MessageType, MessageBody, SentBy, Status)
               VALUES (?,?,?,?,?,?,?)""",
            client_id, invoice_id, mobile, msg_type, body, user, "link_opened")
        conn.commit()


def whatsapp_log(limit: int = 100) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT TOP (?) w.*, c.ClientName FROM dbo.WhatsAppLog w
               INNER JOIN dbo.ClientMaster c ON c.ClientId = w.ClientId
               ORDER BY w.SentAt DESC""", limit)
        return _rows(cur)


def overdue_for_whatsapp() -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT ia.*, c.Mobile, c.ClientName
               FROM dbo.vw_InvoiceAgeing ia
               INNER JOIN dbo.ClientMaster c ON c.ClientId = ia.ClientId
               WHERE ia.PendingAmount > 0 AND c.Mobile IS NOT NULL AND c.Mobile <> ''
               ORDER BY ia.AgeDays DESC""")
        return _rows(cur)


# --- TDS ---------------------------------------------------------------------
def compute_receipt_tds(taxable_amount: float, tds_pct: float = 0,
                        tds_amount_manual: float | None = None,
                        tds_manual: bool = False) -> tuple[float, float]:
    """TDS on net/taxable amount (ex-GST). Returns (tds_amount, taxable_base)."""
    taxable = round(float(taxable_amount or 0), 2)
    if tds_manual and tds_amount_manual is not None:
        return round(float(tds_amount_manual), 2), taxable
    pct = float(tds_pct or 0)
    if pct > 0 and taxable > 0:
        return round(taxable * pct / 100.0, 2), taxable
    if tds_amount_manual is not None and float(tds_amount_manual) > 0:
        return round(float(tds_amount_manual), 2), taxable
    return 0.0, taxable


def add_receipt_with_tds(client_id, receipt_date, amount_received, payment_mode,
                         invoice_amount=0, tds_pct=0, reference="", remarks="",
                         receipt_number=None, created_by="",
                         invoice_ids: list[int] | None = None,
                         taxable_amount: float | None = None,
                         tds_amount_manual: float | None = None,
                         tds_manual: bool = False,
                         gst_amount: float = 0,
                         gst_paid_amount: float = 0,
                         gst_paid_status: str = "unknown") -> str:
    import ledger_service as ls
    taxable = float(taxable_amount if taxable_amount is not None else invoice_amount or 0)
    tds_amt, taxable = compute_receipt_tds(taxable, tds_pct, tds_amount_manual, tds_manual)
    fy = _financial_year(_parse_date(receipt_date))
    rnum = receipt_number or ls.next_receipt_number()
    rdate = _parse_date(receipt_date) or date.today()
    gst_status = (gst_paid_status or "unknown").strip().lower()
    if gst_status not in ("none", "partial", "full", "unknown"):
        gst_status = "unknown"
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dbo.Receipts
               (ClientId,ReceiptNumber,ReceiptDate,AmountReceived,PaymentMode,
                ReferenceNumber,Remarks,CreatedBy,InvoiceAmount,TdsPercentage,TdsAmount,
                FinancialYear,TaxableAmount,TdsManual,GstAmount,GstPaidAmount,GstPaidStatus)
               OUTPUT INSERTED.ReceiptId
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            client_id, rnum, rdate, amount_received, payment_mode,
            reference or None, remarks or None, created_by or None,
            taxable, tds_pct, tds_amt, fy, taxable,
            1 if tds_manual else 0,
            float(gst_amount or 0), float(gst_paid_amount or 0), gst_status)
        receipt_id = int(cur.fetchone()[0])
        ls._allocate_receipt(cur, receipt_id, client_id, float(amount_received),
                             invoice_ids, tds_amount=tds_amt)
        conn.commit()
    return rnum


def update_receipt_with_tds(receipt_id: int, client_id: int, receipt_date,
                            amount_received: float, payment_mode: str,
                            taxable_amount: float, tds_pct: float = 0,
                            tds_amount_manual: float | None = None,
                            tds_manual: bool = False,
                            reference: str = "", remarks: str = "",
                            receipt_number: str | None = None,
                            invoice_ids: list[int] | None = None,
                            gst_amount: float = 0,
                            gst_paid_amount: float = 0,
                            gst_paid_status: str = "unknown") -> None:
    import ledger_service as ls
    existing = ls.get_receipt(receipt_id)
    if not existing:
        raise ValueError("Receipt not found.")
    tds_amt, taxable = compute_receipt_tds(
        taxable_amount, tds_pct, tds_amount_manual, tds_manual)
    rdate = _parse_date(receipt_date) or date.today()
    fy = _financial_year(rdate)
    gst_status = (gst_paid_status or "unknown").strip().lower()
    if gst_status not in ("none", "partial", "full", "unknown"):
        gst_status = "unknown"
    rnum = (receipt_number or existing["ReceiptNumber"]).strip()
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """UPDATE dbo.Receipts SET
               ClientId=?, ReceiptNumber=?, ReceiptDate=?, AmountReceived=?,
               PaymentMode=?, ReferenceNumber=?, Remarks=?,
               InvoiceAmount=?, TaxableAmount=?, TdsPercentage=?, TdsAmount=?,
               TdsManual=?, FinancialYear=?, GstAmount=?, GstPaidAmount=?, GstPaidStatus=?
               WHERE ReceiptId=?""",
            client_id, rnum, rdate, amount_received, payment_mode,
            reference or None, remarks or None,
            taxable, taxable, tds_pct, tds_amt,
            1 if tds_manual else 0, fy,
            float(gst_amount or 0), float(gst_paid_amount or 0), gst_status,
            receipt_id)
        cur.execute("DELETE FROM dbo.ReceiptInvoiceAllocations WHERE ReceiptId=?", receipt_id)
        cur.execute("DELETE FROM dbo.ReceiptNonGstAllocations WHERE ReceiptId=?", receipt_id)
        ls._allocate_receipt(cur, receipt_id, client_id, float(amount_received),
                             invoice_ids, tds_amount=tds_amt)
        conn.commit()


def tds_dashboard() -> dict:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT ISNULL(SUM(TdsAmount),0) AS TotalTds,
                      ISNULL(SUM(CASE WHEN TdsCertificateReceived=0 AND TdsAmount>0
                                 THEN TdsAmount ELSE 0 END),0) AS TdsPendingCert
               FROM dbo.Receipts""")
        return _row(cur) or {}


def tds_client_summary() -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dbo.vw_TdsSummary ORDER BY TotalTds DESC")
        return _rows(cur)


def tds_pending_certificates() -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT r.*, c.ClientName FROM dbo.Receipts r
               INNER JOIN dbo.ClientMaster c ON c.ClientId = r.ClientId
               WHERE r.TdsAmount > 0 AND r.TdsCertificateReceived = 0
               ORDER BY r.ReceiptDate DESC""")
        return _rows(cur)


def mark_tds_certificate(receipt_id: int, cert_no: str, cert_date: str) -> None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """UPDATE dbo.Receipts SET TdsCertificateReceived=1,
               TdsCertificateNo=?, TdsCertificateDate=? WHERE ReceiptId=?""",
            cert_no, _parse_date(cert_date), receipt_id)
        conn.commit()


# --- GST ---------------------------------------------------------------------
def gst_summary() -> dict:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dbo.vw_GstReceivableSummary")
        return _row(cur) or {}


def gst_month_wise(year: int | None = None) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetGstMonthWise ?", year)
        return _rows(cur)


def gst_client_wise() -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetGstClientWise")
        return _rows(cur)


# --- Profitability -----------------------------------------------------------
def list_project_costs(client_id: int | None = None) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        if client_id:
            cur.execute("SELECT * FROM dbo.vw_ClientProfitability WHERE ClientId=? ORDER BY PeriodYear DESC, PeriodMonth DESC", client_id)
        else:
            cur.execute("SELECT * FROM dbo.vw_ClientProfitability ORDER BY GrossProfit DESC")
        return _rows(cur)


def save_project_cost(client_id, project_name, year, month, revenue, consultancy,
                      manhours, employee, travel, misc, user="") -> None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """MERGE dbo.ProjectCosts AS t
               USING (SELECT ? AS ClientId, ? AS ProjectName, ? AS Y, ? AS M) AS s
               ON t.ClientId=s.ClientId AND t.ProjectName=s.ProjectName
                  AND t.PeriodYear=s.Y AND t.PeriodMonth=s.M
               WHEN MATCHED THEN UPDATE SET
                 Revenue=?, ConsultancyCharges=?, Manhours=?, EmployeeCost=?,
                 TravelCost=?, MiscellaneousCost=?, UpdatedBy=?
               WHEN NOT MATCHED THEN INSERT
                 (ClientId,ProjectName,PeriodYear,PeriodMonth,Revenue,ConsultancyCharges,
                  Manhours,EmployeeCost,TravelCost,MiscellaneousCost,UpdatedBy)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?);""",
            client_id, project_name, year, month,
            revenue, consultancy, manhours, employee, travel, misc, user,
            client_id, project_name, year, month, revenue, consultancy,
            manhours, employee, travel, misc, user)
        conn.commit()


def profitability_top_bottom(n: int = 10, segment_id: int | None = None) -> tuple[list[dict], list[dict]]:
    import segment_service as seg
    rows = seg.segment_profitability(segment_id)
    by_profit = sorted(rows, key=lambda r: float(r.get("Profit") or 0), reverse=True)
    top = by_profit[:n]
    bottom = sorted(by_profit, key=lambda r: float(r.get("ProfitPercent") or 0))[:n]
    return top, bottom


# --- Executive ---------------------------------------------------------------
def executive_summary() -> dict:
    if db.use_snapshot_fallback():
        import vercel_snapshot as vs
        return vs.executive_summary()
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dbo.vw_ExecutiveDashboard")
        return _row(cur) or {}


def executive_charts() -> dict[str, list]:
    data: dict[str, list] = {
        "revenue": [], "collections": [], "top_revenue": [], "top_outstanding": [],
        "segment_revenue": [], "segment_expense": [],
    }
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_GetExecutiveCharts")
        data["revenue"] = _rows(cur)
        if cur.nextset():
            data["collections"] = _rows(cur)
        if cur.nextset():
            data["top_revenue"] = _rows(cur)
        if cur.nextset():
            data["top_outstanding"] = _rows(cur)
        if cur.nextset():
            data["segment_revenue"] = _rows(cur)
        if cur.nextset():
            data["segment_expense"] = _rows(cur)
    return data


def audit_log(limit: int = 200) -> list[dict]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT TOP (?) * FROM dbo.AuditLog ORDER BY CreatedAt DESC", limit)
        return _rows(cur)
