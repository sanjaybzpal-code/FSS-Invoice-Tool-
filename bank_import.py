"""Bank statement parser, client matcher, TDS/GST detector for FSS Invoice Tool.

Supports: Excel (.xlsx/.xls), CSV, PDF (via pdfplumber).
Auto-detects: SBI, HDFC, ICICI, Axis, Kotak, Yes, PNB — generic fallback.

Indian TDS/GST calculation logic:
  TDS is deducted on taxable amount only (CBDT Circular 01/2014, NOT on GST).
  Received = Taxable*(1 + GST_rate - TDS_rate)   [if client paid GST]
  Received = Taxable*(1 - TDS_rate)               [if client did NOT pay GST]
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from datetime import date, datetime

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
IMPORT_TMP_DIR = os.path.join(HERE, "temp_imports")

COMMON_TDS_RATES = [0.0, 2.0, 5.0, 7.5, 10.0, 20.0]
COMMON_GST_RATES = [0.0, 5.0, 12.0, 18.0, 28.0]
MATCH_THRESHOLD = 1.0   # rupees tolerance for amount matching


# ─── Date / Amount helpers ────────────────────────────────────────────────────

def _parse_date_flex(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip().rstrip(".")
    for fmt in (
        "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y",
        "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %y",
    ):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _clean_amount(value) -> float | None:
    if value is None:
        return None
    s = str(value).replace(",", "").replace("\xa0", "").strip()
    if s in ("", "-", "nan", "NaN", "None", "0", "0.00", "0.0", "CR", "DR"):
        return None
    # Remove trailing CR/DR indicator (some banks append it)
    s = re.sub(r"(CR|DR)$", "", s, flags=re.IGNORECASE).strip()
    try:
        v = float(s)
        return round(v, 2) if v > 0 else None
    except (ValueError, TypeError):
        return None


def _extract_reference(narration: str) -> str:
    """Extract UTR / NEFT / IMPS / UPI reference from narration text."""
    if not narration:
        return ""
    narration = str(narration)
    patterns = [
        r'\bUTR[:\s#/]*([A-Z0-9]{10,22})\b',
        r'\bIMPS[:/\s]*([0-9]{10,20})\b',
        r'\bNEFT[:/\s]*([A-Z0-9]{10,22})\b',
        r'\bRTGS[:/\s]*([A-Z0-9]{10,22})\b',
        r'\bUPI[:/\s-]*([A-Za-z0-9@._\-]{5,50})',
        r'\bREF[:\s#.]*([A-Z0-9]{6,22})\b',
        r'\bCHQ[:\s#]*([A-Z0-9]{6,20})\b',
        r'\b([A-Z]{4}[0-9]{14,18})\b',   # generic bank ref e.g. HDFC0001234567890123
        r'\b([0-9]{12,20})\b',            # plain numeric reference
    ]
    for p in patterns:
        m = re.search(p, narration, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


# ─── Bank format definitions ──────────────────────────────────────────────────

BANK_FORMATS: dict[str, dict] = {
    "SBI": {
        "date_cols":   ["Txn Date", "Value Date", "Transaction Date", "Date"],
        "narr_cols":   ["Description", "Particulars", "Narration", "Transaction Narration"],
        "credit_cols": ["Credit", "Credit(INR)", "Deposit Amount", "Credit Amount"],
        "debit_cols":  ["Debit", "Debit(INR)", "Withdrawal Amount"],
        "ref_cols":    ["Ref No./Cheque No.", "Ref No", "Cheque Number", "Reference No"],
    },
    "HDFC": {
        "date_cols":   ["Date"],
        "narr_cols":   ["Narration"],
        "credit_cols": ["Deposit Amt.", "Deposit Amount", "Credit Amount", "Credit"],
        "debit_cols":  ["Withdrawal Amt.", "Withdrawal Amount", "Debit Amount", "Debit"],
        "ref_cols":    ["Chq./Ref.No.", "Chq/Ref Number", "Reference No"],
    },
    "ICICI": {
        "date_cols":   ["Transaction Date", "Value Date"],
        "narr_cols":   ["Transaction Remarks", "Narration", "Particulars"],
        "credit_cols": ["Deposit Amount (INR )", "Deposit Amount(INR)", "Credit Amount", "Deposit Amt"],
        "debit_cols":  ["Withdrawal Amount (INR )", "Withdrawal Amount(INR)", "Debit Amount"],
        "ref_cols":    ["Reference Number", "Cheque Number", "Reference No"],
    },
    "AXIS": {
        "date_cols":   ["Tran Date", "Transaction Date", "Value Date"],
        "narr_cols":   ["PARTICULARS", "Narration", "Description"],
        "credit_cols": ["CR", "Credit Amount", "Deposit Amount", "Credit"],
        "debit_cols":  ["DR", "Debit Amount", "Withdrawal Amount", "Debit"],
        "ref_cols":    ["Chq No", "Reference Number", "UTR No"],
    },
    "KOTAK": {
        "date_cols":   ["Transaction Date", "Value Date", "Date"],
        "narr_cols":   ["Description", "Narration", "Particulars"],
        "credit_cols": ["Credit", "Deposit Amount", "Credit Amount"],
        "debit_cols":  ["Debit", "Withdrawal Amount", "Debit Amount"],
        "ref_cols":    ["Reference Number", "Chq/Ref No"],
    },
    "YES": {
        "date_cols":   ["Transaction Date", "Date", "Value Date"],
        "narr_cols":   ["Narration", "Description", "Particulars"],
        "credit_cols": ["Credit", "Deposit Amount", "Credit Amount"],
        "debit_cols":  ["Debit", "Withdrawal Amount"],
        "ref_cols":    ["Reference", "Chq No", "UTR"],
    },
    "PNB": {
        "date_cols":   ["Value Date", "Transaction Date", "Date"],
        "narr_cols":   ["Narration", "Description", "Particulars"],
        "credit_cols": ["Credit", "Deposit Amount"],
        "debit_cols":  ["Debit", "Withdrawal Amount"],
        "ref_cols":    ["Ref No", "Transaction Id", "Reference No"],
    },
}


def _norm_col(s: str) -> str:
    return re.sub(r"[\s\(\)\[\].,/]+", "", str(s)).upper()


def _find_col(headers: list[str], candidates: list[str]) -> str | None:
    norm_h = {_norm_col(h): h for h in headers}
    for cand in candidates:
        nc = _norm_col(cand)
        if nc in norm_h:
            return norm_h[nc]
    # Partial match fallback
    for cand in candidates:
        nc = _norm_col(cand)
        for nh, orig in norm_h.items():
            if nc in nh or nh in nc:
                return orig
    return None


def detect_format(headers: list[str]) -> tuple[str, dict]:
    """Identify bank from column headers. Returns (bank_name, col_map)."""
    best_bank, best_score = "GENERIC", 0
    for bank, fmtdef in BANK_FORMATS.items():
        score = sum(
            1 for col_list in fmtdef.values()
            if any(_norm_col(c) in {_norm_col(h) for h in headers} for c in col_list)
        )
        if score > best_score:
            best_score, best_bank = score, bank

    fmtdef = BANK_FORMATS.get(best_bank, BANK_FORMATS["SBI"])
    col_map = {
        "date":   _find_col(headers, fmtdef["date_cols"]),
        "narr":   _find_col(headers, fmtdef["narr_cols"]),
        "credit": _find_col(headers, fmtdef["credit_cols"]),
        "debit":  _find_col(headers, fmtdef.get("debit_cols", [])),
        "ref":    _find_col(headers, fmtdef.get("ref_cols", [])),
    }
    # Generic fallbacks
    if not col_map["credit"]:
        col_map["credit"] = _find_col(headers,
            ["Credit", "Deposit", "CR", "Credited", "Deposit Amount", "Credit Amount"])
    if not col_map["date"]:
        col_map["date"] = _find_col(headers,
            ["Date", "Transaction Date", "Value Date", "Txn Date"])
    if not col_map["narr"]:
        col_map["narr"] = _find_col(headers,
            ["Narration", "Description", "Particulars", "Remarks", "Details", "Transaction Details"])
    return best_bank, col_map


# ─── Header-row finder ────────────────────────────────────────────────────────

def _find_header_row_in_rows(rows_data: list[list]) -> tuple[int, list[str]]:
    """Find the first row that looks like a bank statement header."""
    date_kws = {"date", "tran", "txn", "value"}
    amount_kws = {"credit", "debit", "deposit", "withdrawal", "amount", "cr", "dr", "balance"}
    for i, row in enumerate(rows_data):
        vals_lower = [str(v or "").strip().lower() for v in row]
        has_date = any(any(k in v for k in date_kws) for v in vals_lower if v)
        has_amt = any(any(k in v for k in amount_kws) for v in vals_lower if v)
        if has_date and has_amt:
            return i, [str(v or "").strip() for v in row]
    return 0, [str(v or "").strip() for v in (rows_data[0] if rows_data else [])]


# ─── Excel parser ─────────────────────────────────────────────────────────────

def _parse_xlsx(file_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    all_rows = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()

    header_idx, headers = _find_header_row_in_rows(all_rows)
    bank, col_map = detect_format(headers)

    if not col_map.get("credit") or not col_map.get("date"):
        return bank, []

    header_map = {h: i for i, h in enumerate(headers)}
    rows: list[dict] = []

    for raw in all_rows[header_idx + 1:]:
        if not any(raw):
            continue

        def g(key):
            col = col_map.get(key)
            if col and col in header_map:
                idx = header_map[col]
                return raw[idx] if idx < len(raw) else None
            return None

        dt = _parse_date_flex(g("date"))
        credit = _clean_amount(g("credit"))
        narr = str(g("narr") or "").strip()
        ref_val = str(g("ref") or "").strip() or _extract_reference(narr)

        if dt and credit and credit > 0:
            rows.append({"date": dt.strftime("%d-%m-%Y"), "narration": narr,
                         "amount": credit, "reference": ref_val})
    return bank, rows


# ─── CSV parser ───────────────────────────────────────────────────────────────

def _parse_csv(file_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    text = file_bytes.decode("utf-8-sig", errors="ignore")
    lines = text.splitlines()

    date_kws = {"date", "tran", "txn", "value"}
    amount_kws = {"credit", "debit", "deposit", "withdrawal", "amount", "cr", "dr"}
    header_idx = 0
    for i, line in enumerate(lines):
        vals_lower = [v.strip().lower() for v in line.split(",")]
        if (any(any(k in v for k in date_kws) for v in vals_lower)
                and any(any(k in v for k in amount_kws) for v in vals_lower)):
            header_idx = i
            break

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    headers = list(reader.fieldnames or [])
    bank, col_map = detect_format(headers)
    rows: list[dict] = []

    for row in reader:
        dt = _parse_date_flex(row.get(col_map.get("date") or "", ""))
        credit = _clean_amount(row.get(col_map.get("credit") or "", ""))
        narr = str(row.get(col_map.get("narr") or "", "") or "").strip()
        ref_col = col_map.get("ref") or ""
        ref_val = str(row.get(ref_col, "") or "").strip() or _extract_reference(narr)
        if dt and credit and credit > 0:
            rows.append({"date": dt.strftime("%d-%m-%Y"), "narration": narr,
                         "amount": credit, "reference": ref_val})
    return bank, rows


# ─── PDF parser ───────────────────────────────────────────────────────────────

def _parse_pdf(file_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    try:
        import pdfplumber
    except ImportError:
        return "PDF", []  # pdfplumber not installed

    rows: list[dict] = []
    bank = "PDF"

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        all_table_rows: list[list] = []
        for page in pdf.pages:
            tables = page.extract_tables()
            for tbl in tables:
                for r in tbl:
                    all_table_rows.append(r)

        if all_table_rows:
            header_idx, headers = _find_header_row_in_rows(all_table_rows)
            bank, col_map = detect_format(headers)
            header_map = {h: i for i, h in enumerate(headers)}

            for raw in all_table_rows[header_idx + 1:]:
                if not any(raw):
                    continue

                def g(key):
                    col = col_map.get(key)
                    if col and col in header_map:
                        idx = header_map[col]
                        return raw[idx] if idx < len(raw) else None
                    return None

                dt = _parse_date_flex(g("date"))
                credit = _clean_amount(g("credit"))
                narr = str(g("narr") or "").strip()
                ref_val = str(g("ref") or "").strip() or _extract_reference(narr)
                if dt and credit and credit > 0:
                    rows.append({"date": dt.strftime("%d-%m-%Y"), "narration": narr,
                                 "amount": credit, "reference": ref_val})
        else:
            # Fallback: unstructured text extraction
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
            rows = _parse_unstructured_text(full_text)

    return bank, rows


def _parse_unstructured_text(text: str) -> list[dict]:
    """Last-resort: parse bank statement from raw text using regex patterns."""
    rows: list[dict] = []
    date_pat = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+\w{3}\s+\d{2,4})'
    amt_pat  = r'([\d,]+\.\d{2})'
    # Look for lines with a date + amount(s)
    for line in text.splitlines():
        dm = re.search(date_pat, line)
        if not dm:
            continue
        amounts = re.findall(amt_pat, line)
        if not amounts:
            continue
        dt = _parse_date_flex(dm.group(1))
        if not dt:
            continue
        # Heuristic: last amount on line often is credit or balance; try second-last
        credit = None
        for a in reversed(amounts):
            v = _clean_amount(a)
            if v and v > 100:  # skip small amounts
                credit = v
                break
        if credit:
            narr = line[dm.end():].strip()[:200]
            ref_val = _extract_reference(narr)
            rows.append({"date": dt.strftime("%d-%m-%Y"), "narration": narr,
                         "amount": credit, "reference": ref_val})
    return rows


# ─── Main entry point ─────────────────────────────────────────────────────────

def parse_statement(file_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    """Parse any supported bank statement. Returns (bank_name, list_of_credit_rows)."""
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".xlsx", ".xls"):
        return _parse_xlsx(file_bytes, filename)
    elif ext == ".csv":
        return _parse_csv(file_bytes, filename)
    elif ext == ".pdf":
        return _parse_pdf(file_bytes, filename)
    return "UNKNOWN", []


# ─── Client matching ──────────────────────────────────────────────────────────

def _tokenize(s: str) -> set[str]:
    stop = {"the", "pvt", "ltd", "llp", "inc", "and", "of", "for", "co",
            "limited", "private", "services", "solutions", "group", "india"}
    tokens = re.sub(r"[^a-z0-9\s]", "", s.lower()).split()
    return {t for t in tokens if len(t) >= 3 and t not in stop}


def match_clients(rows: list[dict], clients: list[dict]) -> list[dict]:
    """Auto-match narration → client. Adds matched_client_id, matched_client_name, match_score."""
    client_data = []
    for c in clients:
        name = c.get("ClientName", "")
        client_data.append({
            "id": c["ClientId"],
            "name": name,
            "tokens": _tokenize(name),
            "norm": re.sub(r"[^a-z0-9]", "", name.lower()),
        })

    result = []
    for row in rows:
        narr_lower = row["narration"].lower()
        narr_norm = re.sub(r"[^a-z0-9]", "", narr_lower)
        narr_tokens = _tokenize(row["narration"])
        best_id, best_name, best_score, best_method = None, "", 0, ""

        for ct in client_data:
            score, method = 0, ""
            if ct["norm"] and len(ct["norm"]) >= 4 and ct["norm"] in narr_norm:
                score, method = 100, "exact"
            else:
                overlap = ct["tokens"] & narr_tokens
                if overlap:
                    score = int(100 * len(overlap) / max(len(ct["tokens"]), 1))
                    method = f"tokens"
            if score > best_score:
                best_score, best_id, best_name, best_method = score, ct["id"], ct["name"], method

        result.append({
            **row,
            "matched_client_id": best_id if best_score >= 30 else None,
            "matched_client_name": best_name if best_score >= 30 else "",
            "match_score": best_score,
            "match_method": best_method,
        })
    return result


# ─── Duplicate detection ─────────────────────────────────────────────────────

def find_duplicates(rows: list[dict]) -> list[dict]:
    """Flag rows where same (client, date, amount) receipt already exists in DB."""
    import db
    from ledger_service import _parse_date
    result = []
    for row in rows:
        is_dup, dup_rcp = False, ""
        cid = row.get("matched_client_id")
        if cid:
            try:
                dt = _parse_date(row["date"])
                with db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """SELECT TOP 1 ReceiptNumber FROM dbo.Receipts
                           WHERE ClientId=? AND ReceiptDate=? AND AmountReceived=?""",
                        cid, dt, float(row["amount"]))
                    ex = cur.fetchone()
                    if ex:
                        is_dup, dup_rcp = True, str(ex[0])
            except Exception:
                pass
        result.append({**row, "is_duplicate": is_dup, "duplicate_receipt_no": dup_rcp})
    return result


# ─── TDS / GST suggestion ────────────────────────────────────────────────────

def suggest_tds_gst(client_id: int | None, amount: float) -> dict:
    """
    Given the credited amount, try to match it to a pending invoice for this client
    and suggest TDS%, GST rate, and whether GST was paid.

    Returns dict with keys: tds_pct, gst_rate, gst_paid, taxable, invoice_total, confidence
    """
    default = {"tds_pct": 0.0, "gst_rate": 18.0, "gst_paid": True,
               "taxable": amount, "invoice_total": amount, "confidence": "low"}
    if not client_id or amount <= 0:
        return default

    # Load pending invoices for this client
    pending: list[dict] = []
    try:
        import db
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT i.TaxableAmount, i.CGSTAmount, i.SGSTAmount, i.IGSTAmount,
                          i.TotalAmount, i.SupplyType,
                          i.TotalAmount - ISNULL(SUM(ria.AllocatedAmount),0) AS Pending
                   FROM dbo.TaxInvoices i
                   LEFT JOIN dbo.ReceiptInvoiceAllocations ria ON ria.InvoiceId = i.InvoiceId
                   WHERE i.ClientId = ?
                   GROUP BY i.TaxableAmount,i.CGSTAmount,i.SGSTAmount,i.IGSTAmount,
                            i.TotalAmount,i.SupplyType
                   HAVING i.TotalAmount - ISNULL(SUM(ria.AllocatedAmount),0) > 0.01""",
                client_id)
            from ledger_service import _rows
            pending = _rows(cur)
    except Exception:
        pass

    best = None
    best_diff = float("inf")
    best_params: dict = {}

    for inv in pending:
        taxable = float(inv.get("TaxableAmount") or 0)
        gst_amt = float((inv.get("CGSTAmount") or 0) + (inv.get("SGSTAmount") or 0)
                        + (inv.get("IGSTAmount") or 0))
        inv_total = float(inv.get("TotalAmount") or 0)
        gst_rate = round((gst_amt / taxable * 100) if taxable else 18.0, 0)

        for tds_pct in COMMON_TDS_RATES:
            # Case 1: GST paid, TDS deducted on taxable
            if taxable > 0:
                expected1 = taxable * (1 + gst_rate/100 - tds_pct/100)
                diff1 = abs(expected1 - amount)
                if diff1 < best_diff:
                    best_diff = diff1
                    best_params = {"tds_pct": tds_pct, "gst_rate": gst_rate, "gst_paid": True,
                                   "taxable": taxable, "invoice_total": inv_total,
                                   "confidence": "high" if diff1 < MATCH_THRESHOLD else "medium"}
                # Case 2: GST NOT paid, TDS deducted on taxable
                expected2 = taxable * (1 - tds_pct/100)
                diff2 = abs(expected2 - amount)
                if diff2 < best_diff:
                    best_diff = diff2
                    best_params = {"tds_pct": tds_pct, "gst_rate": gst_rate, "gst_paid": False,
                                   "taxable": taxable, "invoice_total": inv_total,
                                   "confidence": "high" if diff2 < MATCH_THRESHOLD else "medium"}

    if best_params and best_diff < amount * 0.05:  # within 5% tolerance
        return best_params
    # Fallback: no invoice match, try common rate combos on bare amount
    for tds_pct in COMMON_TDS_RATES:
        for gst_paid in (True, False):
            for gst_rate in (18.0, 9.0, 5.0, 0.0):
                if gst_paid and gst_rate > 0:
                    taxable = amount / (1 + gst_rate/100 - tds_pct/100)
                else:
                    if tds_pct > 0:
                        taxable = amount / (1 - tds_pct/100)
                    else:
                        taxable = amount
                check = taxable * (1 + (gst_rate/100 if gst_paid else 0) - tds_pct/100)
                if abs(check - amount) < MATCH_THRESHOLD and taxable > 0:
                    inv_total = taxable * (1 + gst_rate/100) if gst_rate else taxable
                    return {"tds_pct": tds_pct, "gst_rate": gst_rate, "gst_paid": gst_paid,
                            "taxable": round(taxable, 2), "invoice_total": round(inv_total, 2),
                            "confidence": "medium"}
    return default


# ─── Temp file store ─────────────────────────────────────────────────────────

def save_parsed(data: list[dict]) -> str:
    token = uuid.uuid4().hex
    os.makedirs(IMPORT_TMP_DIR, exist_ok=True)
    path = os.path.join(IMPORT_TMP_DIR, f"{token}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, default=str)
    return token


def load_parsed(token: str) -> list[dict]:
    path = os.path.join(IMPORT_TMP_DIR, f"{token}.json")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def delete_parsed(token: str) -> None:
    try:
        os.remove(os.path.join(IMPORT_TMP_DIR, f"{token}.json"))
    except OSError:
        pass
