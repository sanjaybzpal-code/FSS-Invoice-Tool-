# Accounts Receivable & Management System (Modules 1–7)

Implemented on the **FSS Invoice Tool** (Flask + SQL Server).  
There is no separate Streamlit codebase in this workspace; all modules use the same `FSSInvoice` database.

## Setup

1. Run `Setup Database.bat` (applies scripts `01`–`07`).
2. Configure `config.json`:
   - `database` — SQL Server connection
   - `email` — SMTP for automatic payment reminders
   - `reminders.payment_terms_days` — default due date offset (30 days)

## Module map

| Module | Menu path | SQL |
|--------|-----------|-----|
| 1 Payment Reminders | Accounts → Reminders | `ReminderHistory`, `sp_GetReminderDashboard` |
| 2 WhatsApp | Accounts → WhatsApp | `WhatsAppLog`, wa.me links |
| 3 TDS | Accounts → TDS + Receipts form | `Receipts` TDS columns, `vw_TdsSummary` |
| 4 GST Receivable | Accounts → GST | `vw_GstReceivable`, `vw_GstReceivableSummary` |
| 5 Profitability | Accounts → Profitability | `ProjectCosts`, `vw_ClientProfitability` |
| 6 Executive | Accounts → Executive | `vw_ExecutiveDashboard`, `sp_GetExecutiveCharts` |
| 7 Security | Team roles + Audit + Backup | `AuditLog`, `auth.json` roles, `Backup Database.bat` |

## Roles

| Role | Access |
|------|--------|
| **admin** | Everything including Team & Audit |
| **accounts** | Invoices, receipts, ledger, reminders, TDS, GST |
| **management** | Executive, profitability, reports |
| **viewer** | Read-only views |

Set roles via **Team** page (admin only).

## Email reminders

Rules (automatic when you click **Run Reminders Now**):

- 7 days before due date
- On due date
- 7 / 15 / 30 days after due date

Requires SMTP settings in `config.json`. Invoice PDF is attached when the file path exists.

## WhatsApp

Uses `https://wa.me/` links (no Meta Business API required). Messages and opens are logged in `WhatsAppLog`.

## Backup

Run **`Backup Database.bat`** → saves to `C:\FSS_Backups\`.

Restore via SSMS or:

```sql
RESTORE DATABASE FSSInvoice FROM DISK='C:\FSS_Backups\FSSInvoice_YYYYMMDD.bak' WITH REPLACE;
```

## Python modules

- `ar_service.py` — business logic
- `ar_routes.py` — UI routes
- `audit.py` — audit logging
- `ledger_service.py` — invoices/receipts (extended for due dates & TDS)
