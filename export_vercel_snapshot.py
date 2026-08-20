"""Export local SQL Server data to vercel_data/snapshot.json for Vercel fallback."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal

import db

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "vercel_data")
OUT_FILE = os.path.join(OUT_DIR, "snapshot.json")

TABLES = [
    "BusinessSegments",
    "ClientMaster",
    "TaxInvoices",
    "InvoiceLineItems",
    "Receipts",
    "ReceiptInvoiceAllocations",
    "NonGstBills",
    "ReceiptNonGstAllocations",
]


def _serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


def _row_dict(cursor, row) -> dict:
    cols = [c[0] for c in cursor.description]
    return {k: _serialize(v) for k, v in zip(cols, row)}


def export_snapshot() -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    data: dict = {"exported_at": datetime.now().isoformat(), "tables": {}}
    with db.get_connection() as conn:
        cur = conn.cursor()
        for table in TABLES:
            try:
                cur.execute(
                    """SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                       WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?""",
                    table,
                )
                if not cur.fetchone():
                    continue
                cur.execute(f"SELECT * FROM dbo.{table}")
                rows = [_row_dict(cur, r) for r in cur.fetchall()]
                data["tables"][table] = rows
            except Exception as exc:  # noqa: BLE001
                data["tables"][table] = {"error": str(exc)}
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    inv = len(data["tables"].get("TaxInvoices", []))
    rcp = len(data["tables"].get("Receipts", []))
    return f"Exported to {OUT_FILE} — {inv} invoices, {rcp} receipts"


if __name__ == "__main__":
    print(export_snapshot())
