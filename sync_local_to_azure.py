"""Copy FSS Invoice data from local SQL Server to Azure SQL (for Vercel).

Run on your PC after Azure SQL is created:
  set AZURE_SQL_HOST=yourserver.database.windows.net
  set AZURE_SQL_USER=fssadmin
  set AZURE_SQL_PASSWORD=YourPassword
  set AZURE_SQL_DATABASE=FSSInvoice
  python sync_local_to_azure.py
"""

from __future__ import annotations

import os
import sys

import db


TABLES = [
    ("BusinessSegments", "BusinessSegmentId", True),
    ("ClientMaster", "ClientId", True),
    ("TaxInvoices", "InvoiceId", True),
    ("InvoiceLineItems", "LineItemId", True),
    ("Receipts", "ReceiptId", True),
    ("NonGstBills", "NonGstBillId", True),
    ("ReceiptNonGstAllocations", "AllocationId", True),
    ("ReceiptInvoiceAllocations", "AllocationId", True),
    ("ExpenseCategories", "CategoryId", True),
    ("Expenses", "ExpenseId", True),
    ("ExpenseSegmentAllocations", "AllocationId", True),
    ("LedgerSequence", "SequenceName", False),
    ("ReminderHistory", "ReminderId", True),
    ("WhatsAppLog", "LogId", True),
    ("ProjectCosts", "ProjectCostId", True),
    ("AuditLog", "AuditId", True),
    ("BankImportLog", "ImportId", True),
]


def _azure_connect():
    os.environ.setdefault("VERCEL_ENV", "production")
    return db.get_connection()


def _local_connect():
    saved = os.environ.pop("VERCEL_ENV", None)
    try:
        return db.get_connection()
    finally:
        if saved:
            os.environ["VERCEL_ENV"] = saved


def _table_exists(cur, name: str, *, pymssql: bool) -> bool:
    ph = "%s" if pymssql else "?"
    cur.execute(
        f"SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME={ph}",
        (name,),
    )
    return cur.fetchone() is not None


def _columns(cur, table: str, *, pymssql: bool) -> list[str]:
    ph = "%s" if pymssql else "?"
    cur.execute(
        f"""SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME={ph}
           ORDER BY ORDINAL_POSITION""",
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def _copy_table(local_cur, azure_cur, table: str, _pk: str, identity: bool) -> int:
    if not _table_exists(local_cur, table, pymssql=False):
        return 0
    if not _table_exists(azure_cur, table, pymssql=True):
        print(f"  skip {table} (not on Azure yet — run db.migrate() first)")
        return 0

    cols = _columns(local_cur, table, pymssql=False)
    if not cols:
        return 0
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))

    local_cur.execute(f"SELECT {col_list} FROM dbo.{table}")
    rows = local_cur.fetchall()
    if not rows:
        return 0

    azure_cur.execute(f"DELETE FROM dbo.{table}")
    if identity:
        azure_cur.execute(f"SET IDENTITY_INSERT dbo.{table} ON")
    for row in rows:
        azure_cur.execute(
            f"INSERT INTO dbo.{table} ({col_list}) VALUES ({placeholders})",
            tuple(row),
        )
    if identity:
        azure_cur.execute(f"SET IDENTITY_INSERT dbo.{table} OFF")
    return len(rows)


def main() -> int:
    if not db.vercel_db_configured():
        print("Set Azure SQL env vars first:")
        print("  AZURE_SQL_HOST, AZURE_SQL_USER, AZURE_SQL_PASSWORD, AZURE_SQL_DATABASE")
        return 1

    print("Testing local SQL Server…")
    ok, msg = db.test_connection()
    if not ok and os.environ.get("VERCEL_ENV"):
        os.environ.pop("VERCEL_ENV", None)
        ok, msg = db.test_connection()
    if not ok:
        print(f"Local DB error: {msg}")
        return 1
    print(f"Local: {msg}")

    os.environ["VERCEL_ENV"] = "production"
    print("Migrating Azure schema…")
    print(db.migrate())

    print("Syncing data…")
    with _local_connect() as local, _azure_connect() as azure:
        lc = local.cursor()
        ac = azure.cursor()
        total = 0
        for table, _pk, identity in TABLES:
            try:
                n = _copy_table(lc, ac, table, _pk, identity)
                if n:
                    print(f"  {table}: {n} rows")
                    total += n
                azure.commit()
            except Exception as exc:  # noqa: BLE001
                azure.rollback()
                print(f"  {table}: ERROR {exc}")
        ac.close()
        lc.close()

    print(f"Done — {total} rows copied. Add the same env vars on Vercel and redeploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
