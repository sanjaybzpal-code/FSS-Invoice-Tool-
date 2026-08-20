"""Build a print-ready PDF tax invoice with reportlab, mirroring the Excel layout."""

from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from numwords import rupees_in_words
from invoice_core import compute_totals

NAVY = colors.HexColor("#1F3864")
NAVY2 = colors.HexColor("#2E5496")
LIGHT = colors.HexColor("#DDEBF7")
GREY = colors.HexColor("#F2F2F2")
LINE = colors.HexColor("#9aa3b2")

_S = lambda **k: ParagraphStyle("s", **k)  # noqa: E731


def _money(n: float) -> str:
    return f"{float(n):,.2f}"


def generate_pdf_invoice(config: dict, client, invoice_number: str,
                         invoice_date: str, line_items: list[dict],
                         output_path: str, document_type: str = "tax"):
    seller = config["seller"]
    t = compute_totals(config, client, line_items)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=f"Invoice {invoice_number}", author=seller["name"])
    width = doc.width
    elems = []

    title = _S(fontName="Helvetica-Bold", fontSize=18, textColor=NAVY,
               alignment=TA_CENTER, leading=24, spaceAfter=8)
    sub = _S(fontName="Helvetica", fontSize=9, alignment=TA_CENTER, leading=12)
    white_b = _S(fontName="Helvetica-Bold", fontSize=12, textColor=colors.white,
                 alignment=TA_CENTER)
    lbl = _S(fontName="Helvetica-Bold", fontSize=9, textColor=NAVY)
    norm = _S(fontName="Helvetica", fontSize=9, leading=12)
    norm_b = _S(fontName="Helvetica-Bold", fontSize=10, leading=13)
    cell = _S(fontName="Helvetica", fontSize=9, leading=11)
    cell_r = _S(fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)
    words_st = _S(fontName="Helvetica-BoldOblique", fontSize=9, leading=12)

    # --- Header -----------------------------------------------------------
    elems.append(Paragraph(seller["name"], title))
    elems.append(Paragraph(
        f"{seller['address_line1']}, {seller['address_line2']}", sub))
    elems.append(Paragraph(
        f"Mobile: {seller['mobile']} &nbsp;|&nbsp; E-mail: {seller['email']}"
        f" &nbsp;|&nbsp; GSTIN: {seller['gstin']}", sub))
    elems.append(Spacer(1, 6))

    is_proforma = (document_type or "tax").lower() == "proforma"
    banner_text = "PROFORMA INVOICE" if is_proforma else "TAX INVOICE"
    banner = Table([[Paragraph(banner_text, white_b)]], colWidths=[width])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY2),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elems.append(banner)
    if is_proforma:
        disc = _S(fontName="Helvetica-Oblique", fontSize=8, textColor=colors.HexColor("#B45309"),
                   alignment=TA_CENTER)
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(
            "This is NOT a Tax Invoice — for client approval only. "
            "GST will be charged when the final tax invoice is issued.", disc))
    elems.append(Spacer(1, 8))

    # --- Bill-to + meta ---------------------------------------------------
    bill_to = [
        Paragraph("Bill To:", lbl),
        Paragraph(client.name, norm_b),
        Paragraph(client.address or "", norm),
        Paragraph(f"GSTIN: {client.gstin or '-'}", lbl),
    ]
    meta_rows = [
        [Paragraph("Invoice No.:", lbl), Paragraph(str(invoice_number), norm)],
        [Paragraph("Invoice Date:", lbl), Paragraph(invoice_date, norm)],
        [Paragraph("GST Type:", lbl),
         Paragraph("CGST + SGST" if t.intra else "IGST", norm)],
        [Paragraph("Supply Type:", lbl),
         Paragraph("Intra-State" if t.intra else "Inter-State", norm)],
    ]
    meta = Table(meta_rows, colWidths=[width * 0.18, width * 0.20])
    meta.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    head = Table([[bill_to, meta]], colWidths=[width * 0.58, width * 0.42])
    head.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(head)
    elems.append(Spacer(1, 10))

    # --- Items + totals ---------------------------------------------------
    data = [[Paragraph("<b>Sr.</b>", _S(fontName="Helvetica-Bold", fontSize=9,
                                        textColor=colors.white, alignment=TA_CENTER)),
             Paragraph("<b>Particulars</b>", _S(fontName="Helvetica-Bold",
                                                fontSize=9, textColor=colors.white)),
             Paragraph("<b>Work Date</b>", _S(fontName="Helvetica-Bold", fontSize=9,
                                              textColor=colors.white, alignment=TA_CENTER)),
             Paragraph("<b>Amount (Rs.)</b>", _S(fontName="Helvetica-Bold",
                                                 fontSize=9, textColor=colors.white,
                                                 alignment=TA_RIGHT))]]
    for i, it in enumerate(line_items, 1):
        data.append([
            Paragraph(str(i), _S(fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
            Paragraph(it["particulars"], cell),
            Paragraph(it.get("date", ""), _S(fontName="Helvetica", fontSize=9,
                                             alignment=TA_CENTER)),
            Paragraph(_money(it["amount"]), cell_r),
        ])

    n_items = len(line_items)
    total_rows = [("Sub Total", t.subtotal, False)]
    total_rows += [(lab, amt, False) for lab, amt in t.tax_lines]
    total_rows.append(("Grand Total", t.total, True))
    for label, amount, bold in total_rows:
        st = _S(fontName="Helvetica-Bold" if bold else "Helvetica",
                fontSize=10 if bold else 9, alignment=TA_RIGHT)
        # label in col 2, amount in col 3 (right-hand totals block, fully bordered)
        data.append(["", "", Paragraph(label, st), Paragraph(_money(amount), st)])

    col_w = [width * 0.08, width * 0.50, width * 0.22, width * 0.20]
    items = Table(data, colWidths=col_w, repeatRows=1)
    first_total = 1 + n_items
    last_total = first_total + len(total_rows) - 1
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, n_items), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # full borders around the Sub Total / tax / Grand Total block
        ("GRID", (2, first_total), (3, last_total), 0.5, LINE),
    ]
    # highlight grand total
    style.append(("BACKGROUND", (2, last_total), (3, last_total), LIGHT))
    items.setStyle(TableStyle(style))
    elems.append(items)
    elems.append(Spacer(1, 6))

    words = Table([[Paragraph(
        "<b>Amount in words:</b> " + rupees_in_words(t.total), words_st)]],
        colWidths=[width])
    words.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREY),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems.append(words)
    elems.append(Spacer(1, 16))

    # --- Footer: bank (left) + signature/stamp (right) --------------------
    bank = [
        Paragraph("Bank Details:", lbl),
        Paragraph(f"Account Name: {seller['name']}", norm),
        Paragraph(f"Bank: {seller['bank_name']} &nbsp; Branch: {seller['bank_branch']}", norm),
        Paragraph(f"A/C No.: {seller['bank_account']}", norm),
        Paragraph(f"IFSC: {seller['bank_ifsc']}", norm),
        Paragraph(f"GSTIN: {seller['gstin']}", norm),
    ]
    sign_cell = [Paragraph(f"For {seller['name']}",
                           _S(fontName="Helvetica-Bold", fontSize=10,
                              alignment=TA_CENTER))]

    footer = Table([[bank, sign_cell]], colWidths=[width * 0.58, width * 0.42])
    footer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(footer)

    elems.append(Spacer(1, 18))
    note = _S(fontName="Helvetica-Oblique", fontSize=9, textColor=colors.HexColor("#6b7280"),
              alignment=TA_CENTER, leading=12)
    elems.append(Paragraph(
        "This is a computer-generated tax invoice and does not require a "
        "physical signature or company stamp.", note))

    doc.build(elems)
    return t
