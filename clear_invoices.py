"""Delete all tax invoices from DB and local files. Keeps ClientMaster intact."""
from __future__ import annotations

import glob
import json
import os

import db

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
LOG = os.path.join(HERE, "invoices_log.json")


def main() -> None:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dbo.TaxInvoices")
        n = int(cur.fetchone()[0])
        print(f"Invoices in database: {n}")

        # Child / link tables first
        for sql in (
            "DELETE FROM dbo.ReceiptInvoiceAllocations",
            "DELETE FROM dbo.ReminderHistory",
            "DELETE FROM dbo.WhatsAppLog WHERE InvoiceId IS NOT NULL",
            "DELETE FROM dbo.TaxInvoices",  # InvoiceLineItems CASCADE
        ):
            cur.execute(sql)
            print(f"  {sql.split()[2]}: {cur.rowcount} row(s)")
        conn.commit()

    # Local invoice log
    with open(LOG, "w", encoding="utf-8") as fh:
        json.dump([], fh)
    print("Cleared invoices_log.json")

    # Reset next invoice number to 1
    with open(CONFIG, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg.setdefault("invoice", {})["next_number"] = 1
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=4, ensure_ascii=False)
    print("Reset config invoice next_number to 1")

    # Generated PDF/Excel files
    out = os.path.join(HERE, "Invoices")
    removed = 0
    for pattern in ("*.pdf", "*.xlsx"):
        for path in glob.glob(os.path.join(out, pattern)):
            try:
                os.remove(path)
                removed += 1
            except OSError as exc:
                print(f"  Could not delete {path}: {exc}")
    print(f"Removed {removed} file(s) from Invoices folder")

    cur2 = db.get_connection()
    c = cur2.cursor()
    c.execute("SELECT COUNT(*) FROM dbo.ClientMaster")
    clients = int(c.fetchone()[0])
    cur2.close()
    print(f"Clients preserved: {clients}")


if __name__ == "__main__":
    main()
