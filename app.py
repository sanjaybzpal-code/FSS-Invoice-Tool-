"""FSS Invoice Generator - desktop app.

Pick a client (address / GST / tax type fill in automatically), type the
particulars and amounts, and click Generate. A print-ready Excel invoice is
written to the Invoices folder and opened for you.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime

import tkinter as tk
from tkinter import messagebox, ttk

import clients as clients_mod
from generator import generate_invoice

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

ROW_COUNT_START = 6  # initial blank particular rows


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=4, ensure_ascii=False)


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9 _.-]", "", text).strip()
    return re.sub(r"\s+", "_", text)[:60]


class InvoiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FSS Invoice Generator")
        self.geometry("960x720")
        self.minsize(880, 640)
        self.configure(bg="#f4f6fa")

        self.config_data = load_config()
        self.clients: list[clients_mod.Client] = []
        self.client_by_name: dict[str, clients_mod.Client] = {}
        self.item_rows: list[dict] = []

        self._build_styles()
        self._build_header()
        self._build_client_section()
        self._build_items_section()
        self._build_footer()

        self._load_clients()

    # -- styling -----------------------------------------------------------
    def _build_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f4f6fa")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#ffffff", font=("Segoe UI", 10))
        style.configure("Field.TLabel", background="#f4f6fa", font=("Segoe UI", 10))
        style.configure("Head.TLabel", background="#f4f6fa",
                        font=("Segoe UI", 11, "bold"), foreground="#1F3864")
        style.configure("Auto.TLabel", background="#ffffff",
                        font=("Segoe UI", 10), foreground="#404040")
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"))

    def _build_header(self):
        bar = tk.Frame(self, bg="#1F3864", height=58)
        bar.pack(fill="x")
        tk.Label(bar, text="Facade Structural Services  -  Invoice Generator",
                 bg="#1F3864", fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=18, pady=12)

    # -- client section ----------------------------------------------------
    def _build_client_section(self):
        frame = ttk.Frame(self, padding=(16, 12, 16, 4))
        frame.pack(fill="x")

        ttk.Label(frame, text="Client", style="Head.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6), columnspan=4)

        ttk.Label(frame, text="Client Name:", style="Field.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.client_var = tk.StringVar()
        self.client_combo = ttk.Combobox(frame, textvariable=self.client_var,
                                          state="readonly", width=55,
                                          font=("Segoe UI", 10))
        self.client_combo.grid(row=1, column=1, sticky="w", pady=4)
        self.client_combo.bind("<<ComboboxSelected>>", self._on_client_selected)

        ttk.Label(frame, text="Invoice No.:", style="Field.TLabel").grid(
            row=1, column=2, sticky="e", padx=(20, 8), pady=4)
        self.invoice_no_var = tk.StringVar(
            value=str(self.config_data["invoice"]["next_number"]))
        ttk.Entry(frame, textvariable=self.invoice_no_var, width=12,
                  font=("Segoe UI", 10)).grid(row=1, column=3, sticky="w", pady=4)

        # Auto-filled (read-only) info card
        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.grid(row=2, column=0, columnspan=4, sticky="we", pady=(8, 0))
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="GST No.:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w")
        self.gst_lbl = ttk.Label(card, text="-", style="Auto.TLabel")
        self.gst_lbl.grid(row=0, column=1, sticky="w", padx=8)

        ttk.Label(card, text="Tax Type:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=2, sticky="w", padx=(20, 0))
        self.tax_lbl = ttk.Label(card, text="-", style="Auto.TLabel")
        self.tax_lbl.grid(row=0, column=3, sticky="w", padx=8)

        ttk.Label(card, text="Address:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky="nw", pady=(6, 0))
        self.addr_lbl = ttk.Label(card, text="-", style="Auto.TLabel",
                                  wraplength=760, justify="left")
        self.addr_lbl.grid(row=1, column=1, columnspan=3, sticky="w",
                           padx=8, pady=(6, 0))

        # Dates row
        dates = ttk.Frame(self, padding=(16, 8, 16, 0))
        dates.pack(fill="x")
        ttk.Label(dates, text="Invoice Date:", style="Field.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self.inv_date_var = tk.StringVar(value=datetime.today().strftime("%d-%m-%Y"))
        ttk.Entry(dates, textvariable=self.inv_date_var, width=14,
                  font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w")

        ttk.Label(dates, text="Default Work Delivered Date:",
                  style="Field.TLabel").grid(row=0, column=2, sticky="e",
                                             padx=(24, 8))
        self.work_date_var = tk.StringVar(
            value=datetime.today().strftime("%d-%m-%Y"))
        ttk.Entry(dates, textvariable=self.work_date_var, width=14,
                  font=("Segoe UI", 10)).grid(row=0, column=3, sticky="w")
        ttk.Button(dates, text="Apply to all rows",
                   command=self._apply_default_date).grid(row=0, column=4,
                                                          padx=(10, 0))
        ttk.Label(dates, text="(dates as dd-mm-yyyy)",
                  style="Field.TLabel", foreground="#888").grid(
            row=0, column=5, sticky="w", padx=(10, 0))

    # -- line items --------------------------------------------------------
    def _build_items_section(self):
        outer = ttk.Frame(self, padding=(16, 12, 16, 4))
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x")
        ttk.Label(head, text="Particulars", style="Head.TLabel").pack(side="left")
        ttk.Button(head, text="+ Add Row", command=self._add_row).pack(side="right")

        # Column headers
        cols = ttk.Frame(outer, style="Card.TFrame", padding=(8, 6))
        cols.pack(fill="x", pady=(6, 0))
        for text, width, col in (("Sr.", 5, 0), ("Particulars", 56, 1),
                                  ("Work Date", 14, 2), ("Amount (Rs.)", 16, 3),
                                  ("", 4, 4)):
            ttk.Label(cols, text=text, font=("Segoe UI", 10, "bold"),
                      width=width, anchor="w").grid(row=0, column=col, padx=4)

        # Scrollable rows area
        canvas_wrap = ttk.Frame(outer)
        canvas_wrap.pack(fill="both", expand=True)
        self.rows_canvas = tk.Canvas(canvas_wrap, bg="#ffffff",
                                     highlightthickness=1,
                                     highlightbackground="#dfe3ea")
        scroll = ttk.Scrollbar(canvas_wrap, orient="vertical",
                               command=self.rows_canvas.yview)
        self.rows_inner = ttk.Frame(self.rows_canvas, style="Card.TFrame")
        self.rows_inner.bind(
            "<Configure>",
            lambda e: self.rows_canvas.configure(
                scrollregion=self.rows_canvas.bbox("all")))
        self.rows_canvas.create_window((0, 0), window=self.rows_inner,
                                       anchor="nw")
        self.rows_canvas.configure(yscrollcommand=scroll.set)
        self.rows_canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.rows_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        for _ in range(ROW_COUNT_START):
            self._add_row()

    def _on_mousewheel(self, event):
        self.rows_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _add_row(self):
        idx = len(self.item_rows)
        row = ttk.Frame(self.rows_inner, style="Card.TFrame", padding=(6, 3))
        row.pack(fill="x")

        sr = ttk.Label(row, text=str(idx + 1), width=5, anchor="center")
        sr.grid(row=0, column=0, padx=4)

        part_var = tk.StringVar()
        part = ttk.Entry(row, textvariable=part_var, width=58,
                         font=("Segoe UI", 10))
        part.grid(row=0, column=1, padx=4)

        date_var = tk.StringVar(value=self.work_date_var.get())
        date = ttk.Entry(row, textvariable=date_var, width=14,
                         font=("Segoe UI", 10))
        date.grid(row=0, column=2, padx=4)

        amt_var = tk.StringVar()
        amt = ttk.Entry(row, textvariable=amt_var, width=16,
                        font=("Segoe UI", 10), justify="right")
        amt.grid(row=0, column=3, padx=4)
        amt_var.trace_add("write", lambda *_: self._recompute_total())

        record = {"frame": row, "sr": sr, "particulars": part_var,
                  "date": date_var, "amount": amt_var}

        del_btn = ttk.Button(row, text="X", width=3,
                             command=lambda: self._remove_row(record))
        del_btn.grid(row=0, column=4, padx=4)

        self.item_rows.append(record)
        self._renumber()

    def _remove_row(self, record):
        if len(self.item_rows) <= 1:
            return
        record["frame"].destroy()
        self.item_rows.remove(record)
        self._renumber()
        self._recompute_total()

    def _renumber(self):
        for i, rec in enumerate(self.item_rows, start=1):
            rec["sr"].configure(text=str(i))

    def _apply_default_date(self):
        for rec in self.item_rows:
            rec["date"].set(self.work_date_var.get())

    # -- footer / totals ---------------------------------------------------
    def _build_footer(self):
        bar = tk.Frame(self, bg="#eef1f7")
        bar.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value="Loading clients...")
        tk.Label(bar, textvariable=self.status_var, bg="#eef1f7",
                 fg="#555", font=("Segoe UI", 9)).pack(side="left", padx=14,
                                                       pady=10)

        self.total_var = tk.StringVar(value="Grand Total: Rs. 0.00")
        tk.Label(bar, textvariable=self.total_var, bg="#eef1f7", fg="#1F3864",
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=14)

        gen = ttk.Button(bar, text="Generate Invoice", style="Accent.TButton",
                         command=self._generate)
        gen.pack(side="right", padx=14, pady=8)
        ttk.Button(bar, text="Reload Clients",
                   command=self._load_clients).pack(side="right", pady=8)

    def _recompute_total(self):
        subtotal = 0.0
        for rec in self.item_rows:
            try:
                subtotal += float(rec["amount"].get())
            except (ValueError, TypeError):
                continue
        client = self.client_by_name.get(self.client_var.get())
        tax = self.config_data["tax"]
        if client is None:
            total = subtotal
        elif client.mh:
            total = subtotal * (1 + (tax["cgst_rate"] + tax["sgst_rate"]) / 100.0)
        else:
            total = subtotal * (1 + tax["igst_rate"] / 100.0)
        self.total_var.set(f"Grand Total: Rs. {total:,.2f}")

    # -- data --------------------------------------------------------------
    def _load_clients(self):
        wb_rel = self.config_data["paths"]["clients_workbook"]
        wb_path = wb_rel if os.path.isabs(wb_rel) else os.path.join(HERE, wb_rel)
        sheet = self.config_data["paths"]["clients_sheet"]
        try:
            self.clients, msg = clients_mod.load_clients(wb_path, sheet)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Client list error", str(exc))
            self.status_var.set("Could not load clients.")
            return
        self.client_by_name = {c.name: c for c in self.clients}
        names = sorted(self.client_by_name.keys())
        self.client_combo["values"] = names
        self.status_var.set(msg)

    def _on_client_selected(self, _event=None):
        client = self.client_by_name.get(self.client_var.get())
        if not client:
            return
        self.gst_lbl.configure(text=client.gstin or "-")
        self.addr_lbl.configure(text=client.address or "-")
        if client.mh:
            self.tax_lbl.configure(
                text="Maharashtra -> CGST 9% + SGST 9% (Intra-State)")
        else:
            self.tax_lbl.configure(text="Outside Maharashtra -> IGST 18% (Inter-State)")
        self._recompute_total()

    # -- generate ----------------------------------------------------------
    def _collect_items(self):
        items = []
        for rec in self.item_rows:
            particulars = rec["particulars"].get().strip()
            amount_raw = rec["amount"].get().strip()
            if not particulars and not amount_raw:
                continue
            if not particulars:
                raise ValueError("A row has an amount but no particulars.")
            try:
                amount = float(amount_raw)
            except ValueError:
                raise ValueError(f"Invalid amount for: {particulars!r}")
            if amount < 0:
                raise ValueError(f"Amount cannot be negative for: {particulars!r}")
            items.append({"particulars": particulars,
                          "date": rec["date"].get().strip(),
                          "amount": amount})
        return items

    def _generate(self):
        client = self.client_by_name.get(self.client_var.get())
        if client is None:
            messagebox.showwarning("Select client", "Please select a client.")
            return
        invoice_no = self.invoice_no_var.get().strip()
        if not invoice_no:
            messagebox.showwarning("Invoice number", "Enter an invoice number.")
            return
        try:
            items = self._collect_items()
        except ValueError as exc:
            messagebox.showerror("Check entries", str(exc))
            return
        if not items:
            messagebox.showwarning("No items",
                                   "Add at least one particular with an amount.")
            return

        out_folder = self.config_data["paths"]["output_folder"]
        out_folder = (out_folder if os.path.isabs(out_folder)
                      else os.path.join(HERE, out_folder))
        fname = (f"Invoice_{safe_filename(str(invoice_no))}_"
                 f"{safe_filename(client.name)}.xlsx")
        out_path = os.path.join(out_folder, fname)

        try:
            result = generate_invoice(
                self.config_data, client, invoice_no,
                self.inv_date_var.get().strip(), items, out_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Generation failed", str(exc))
            return

        # advance invoice counter if the user used the suggested number
        try:
            if int(invoice_no) >= self.config_data["invoice"]["next_number"]:
                self.config_data["invoice"]["next_number"] = int(invoice_no) + 1
                save_config(self.config_data)
                self.invoice_no_var.set(
                    str(self.config_data["invoice"]["next_number"]))
        except ValueError:
            pass

        self.status_var.set(f"Saved: {os.path.basename(result.path)}")
        if messagebox.askyesno(
                "Invoice created",
                f"Invoice saved to:\n{result.path}\n\n"
                f"Grand Total: Rs. {result.total:,.2f}\n\nOpen it now?"):
            self._open_file(result.path)

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    InvoiceApp().mainloop()
