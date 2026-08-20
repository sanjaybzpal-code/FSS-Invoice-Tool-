# FSS Accounts — SQL Server Ledger Module

## Overview

This module implements Tally-style **Client Ledger & Outstanding Management** for the
FSS Invoice Tool. It uses **SQL Server** database `FSSInvoice` on the host PC.

> **Note:** There is no separate Streamlit application in this workspace. The Accounts
> module is integrated into the **Flask web app** (`web.py`) with the same SQL Server
> backend. All 12 requested features are implemented here.

## Setup

1. Ensure SQL Server is running (local instance detected as `(local)`).
2. Run **`Setup Database.bat`** — executes scripts in order:
   - `01_create_database.sql` — creates `FSSInvoice`
   - `02_tables.sql` — `ClientMaster`, `TaxInvoices`, `InvoiceLineItems`, `Receipts`
   - `03_views.sql` — ledger, outstanding, ageing views
   - `04_stored_procedures.sql` — ledger report, dashboard, ageing SPs
3. Connection settings: `config.json` → `"database"`.

## Feature checklist

| # | Requirement | Implementation |
|---|-------------|----------------|
| 1 | Client Master | `ClientMaster` table + **Accounts → Clients** |
| 2 | Invoice Ledger (auto debit) | `TaxInvoices` + hook in `web.py` `api_generate` |
| 3 | Receipt entry | **Accounts → Receipts** |
| 4 | Outstanding calculation | `vw_ClientOutstanding` view |
| 5 | Client Ledger report | **Accounts → Client Ledger** + `sp_GetClientLedger` |
| 6 | Outstanding dashboard | **Accounts → Dashboard** |
| 7 | Ageing analysis | **Accounts → Ageing** + `vw_InvoiceAgeing` |
| 8 | Ledger PDF | Button on ledger screen → `ledger_reports.py` |
| 9 | PDF + Excel export | `/accounts/ledger/export/pdf` and `/excel` |
| 10 | Client summary | Click client in Outstanding → detail page |
| 11 | SQL tables/views/SPs | `database/` folder |
| 12 | Accounts menu | Top bar **Accounts** + sub-navigation |

## Tables & relationships

```
ClientMaster (1) ──< TaxInvoices (many)
ClientMaster (1) ──< Receipts (many)
TaxInvoices (1) ──< InvoiceLineItems (many)
```

## Python modules

| File | Role |
|------|------|
| `db.py` | Connection, migration runner |
| `ledger_service.py` | CRUD, reports, sync |
| `ledger_reports.py` | PDF / Excel ledger export |
| `accounts.py` | Flask routes (Accounts UI) |

## Backward compatibility

- Invoice generation (PDF/Excel) works even if SQL Server is temporarily unavailable.
- Excel client workbook remains the source for bulk client sync.
- Existing `invoices_log.json` file-based counter is unchanged.

## If you have a separate Streamlit app

Point us to that project folder and the same `database/` scripts and `ledger_service.py`
can be imported into Streamlit pages with `st.session_state` and the same SQL connection.
