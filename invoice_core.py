"""Shared invoice calculations and automatic invoice-number logic.

Used by both the Excel and PDF generators so the two always agree.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER_FILE = os.path.join(HERE, "invoices_log.json")


@dataclass
class Totals:
    subtotal: float
    cgst: float
    sgst: float
    igst: float
    total: float
    intra: bool
    supply_type: str
    tax_lines: list = field(default_factory=list)  # [(label, amount), ...]


def compute_totals(config: dict, client, line_items: list[dict]) -> Totals:
    tax = config["tax"]
    subtotal = round(sum(float(it["amount"]) for it in line_items), 2)

    intra = bool(getattr(client, "mh", False))
    if intra:
        cgst = round(subtotal * tax["cgst_rate"] / 100.0, 2)
        sgst = round(subtotal * tax["sgst_rate"] / 100.0, 2)
        igst = 0.0
        tax_lines = [
            (f"CGST @ {tax['cgst_rate']:g}%", cgst),
            (f"SGST @ {tax['sgst_rate']:g}%", sgst),
        ]
        supply_type = "Intra-State (CGST + SGST)"
    else:
        cgst = sgst = 0.0
        igst = round(subtotal * tax["igst_rate"] / 100.0, 2)
        tax_lines = [(f"IGST @ {tax['igst_rate']:g}%", igst)]
        supply_type = "Inter-State (IGST)"

    total = round(subtotal + cgst + sgst + igst, 2)
    return Totals(subtotal=subtotal, cgst=cgst, sgst=sgst, igst=igst,
                  total=total, intra=intra, supply_type=supply_type,
                  tax_lines=tax_lines)


# --- Automatic invoice numbering ------------------------------------------
def _numbers_from_folder(folder: str) -> list[int]:
    nums = []
    if not os.path.isdir(folder):
        return nums
    for name in os.listdir(folder):
        m = re.match(r"Invoice_(\d+)_", name)
        if m:
            nums.append(int(m.group(1)))
    return nums


def _load_ledger() -> list[dict]:
    if not os.path.exists(LEDGER_FILE):
        return []
    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []


def _numbers_from_ledger() -> list[int]:
    nums = []
    for entry in _load_ledger():
        try:
            nums.append(int(entry.get("number")))
        except (TypeError, ValueError):
            continue
    return nums


def next_invoice_number(config: dict, output_folder: str) -> int:
    """Highest of (config counter, ledger, existing files) + safety, never decreasing."""
    candidates = [int(config["invoice"].get("next_number", 1))]
    existing = _numbers_from_folder(output_folder) + _numbers_from_ledger()
    if existing:
        candidates.append(max(existing) + 1)
    return max(candidates)


def record_invoice(number, client_name: str, total: float,
                   date: str, files: list[str]) -> None:
    """Append a generated invoice to the ledger (audit trail + numbering safety)."""
    ledger = _load_ledger()
    try:
        num = int(number)
    except (TypeError, ValueError):
        num = number
    ledger.append({
        "number": num,
        "client": client_name,
        "total": total,
        "date": date,
        "files": files,
    })
    try:
        with open(LEDGER_FILE, "w", encoding="utf-8") as fh:
            json.dump(ledger, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass
