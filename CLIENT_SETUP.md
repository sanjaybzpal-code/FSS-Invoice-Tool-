# FSS Invoice Tool — Client Installation Guide

Thank you for using **FSS Invoice & Accounts Suite**. Follow these steps on the **server PC** (one computer that stays on during office hours).

---

## Requirements

| Item | Details |
|------|---------|
| **OS** | Windows 10 or 11 |
| **Python** | 3.10+ from [python.org](https://www.python.org/downloads/) — tick **“Add Python to PATH”** |
| **SQL Server** | SQL Server Express (free) or full SQL Server on same PC |
| **ODBC Driver** | [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| **Network** | Office Wi‑Fi/LAN for team access (optional: internet via Cloudflare) |

---

## Install (first time)

1. **Unzip** this folder to e.g. `C:\FSS Invoice Tool\`
2. Open **Command Prompt** in that folder and run:
   ```
   pip install -r requirements.txt
   ```
3. Double-click **`Setup Database.bat`** — creates the `FSSInvoice` database
4. Double-click **`Install FSS Invoice Tool.bat`** — Desktop shortcut
5. Double-click **`FSS Invoice Tool`** (Desktop) — browser opens
6. On first run, **create Admin username & password**

---

## Your company details

Edit **`config.json`** before generating invoices:

- `seller` — your company name, address, GSTIN, bank details
- `tax` — CGST/SGST/IGST rates (default 9/9/18)
- `database` — SQL Server connection (default: local `(local)`)
- `paths.output_folder` — where PDF/Excel invoices are saved

---

## Team access (office network)

1. Run **`Allow on Network (Run as Admin).bat`** once (right-click → Run as administrator)
2. Run **`Show Network Address.bat`** — note the URL e.g. `http://192.168.x.x:5000`
3. Share that URL with your team — each person logs in with their own account
4. Admin creates users at **Team** (`/users`)

For **24/7 server**, run **`Go Live.bat`**.

---

## Access from anywhere (internet)

1. Keep **`Go Live.bat`** / live server running on the office PC
2. Download [cloudflared.exe](https://github.com/cloudflare/cloudflared/releases) into this folder
3. Run **`Go Live - Internet (Cloudflare).bat`**
4. Share the `https://….trycloudflare.com` link with your team (login required)

> Do not share the link publicly — it contains your business data behind login only.

---

## Daily use

| Task | Action |
|------|--------|
| Start app | Desktop shortcut **FSS Invoice Tool** |
| Tax invoice | Home → fill form → Generate |
| Proforma (before GST) | Home → **Proforma Invoice** tab |
| Record payment | Accounts → Receipts |
| Outstanding | Accounts → Outstanding |

---

## Support checklist

| Problem | Fix |
|---------|-----|
| “Database error” | Run `Setup Database.bat`, check SQL Server is running |
| Team cannot open URL | Run firewall bat as Admin; same Wi‑Fi network |
| Old screen after update | `Restart FSS Invoice Tool.bat` + browser Ctrl+F5 |
| Forgot admin password | Delete `auth.json` and restart — setup screen returns |

---

## Files not included (your data stays private)

Each installation starts fresh — no invoices, clients, or passwords from the developer’s copy.

---

*FSS Invoice & Accounts Suite — Flask + SQL Server*
