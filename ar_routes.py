"""AR module routes: reminders, WhatsApp, TDS, GST, profitability, executive."""

from __future__ import annotations

from datetime import date

from flask import (Blueprint, flash, redirect, render_template, request, url_for)

import ar_service as ar
import audit
import auth
import ledger_service as ls

ar_bp = Blueprint("ar", __name__, url_prefix="/accounts")


def _user():
    return auth.current_user()


def _guard(perm: str):
    if not auth.can(_user(), perm) and not auth.is_admin(_user()):
        flash("You do not have permission for this section.")
        return False
    return True


@ar_bp.before_request
@auth.login_required
def _login():
    pass


@ar_bp.route("/reminders")
def reminders():
    if not _guard("reminders"):
        return redirect(url_for("accounts.dashboard"))
    try:
        dash = ar.reminder_dashboard()
        history = ar.reminder_history(50)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        dash, history = {}, []
    return render_template("accounts/reminders.html", dash=dash, history=history,
                           user=_user())


@ar_bp.route("/reminders/run", methods=["POST"])
def reminders_run():
    if not auth.is_admin(_user()) and not auth.can(_user(), "reminders"):
        return redirect(url_for("ar.reminders"))
    results = ar.process_automatic_reminders(_user())
    audit.log(_user(), "run_auto_reminders", details="; ".join(results[:5]))
    flash(f"Processed {len(results)} reminder(s).")
    return redirect(url_for("ar.reminders"))


@ar_bp.route("/whatsapp")
def whatsapp():
    if not _guard("whatsapp"):
        return redirect(url_for("accounts.dashboard"))
    try:
        overdue = ar.overdue_for_whatsapp()
        log = ar.whatsapp_log(50)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        overdue, log = [], []
    links = []
    for row in overdue:
        msg = ar.whatsapp_message(row["ClientName"], row["InvoiceNumber"],
                                  float(row["PendingAmount"]))
        mob = row.get("Mobile") or ""
        links.append({**row, "message": msg, "link": ar.whatsapp_link(mob, msg) if mob else ""})
    return render_template("accounts/whatsapp.html", items=links, log=log, user=_user())


@ar_bp.route("/whatsapp/send", methods=["POST"])
def whatsapp_send():
    cid = int(request.form.get("client_id", 0))
    iid = request.form.get("invoice_id", type=int)
    msg_type = request.form.get("msg_type", "reminder")
    body = request.form.get("message", "")
    mobile = request.form.get("mobile", "")
    ar.log_whatsapp(cid, mobile, msg_type, body, _user(), iid)
    audit.log(_user(), "whatsapp_send", "client", str(cid), msg_type)
    link = request.form.get("wa_link") or ""
    if link.startswith("http"):
        return redirect(link)
    return redirect(url_for("ar.whatsapp"))


@ar_bp.route("/tds")
def tds():
    if not _guard("tds"):
        return redirect(url_for("accounts.dashboard"))
    try:
        dash = ar.tds_dashboard()
        summary = ar.tds_client_summary()
        pending = ar.tds_pending_certificates()
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        dash, summary, pending = {}, [], []
    return render_template("accounts/tds.html", dash=dash, summary=summary,
                           pending=pending, user=_user())


@ar_bp.route("/tds/cert", methods=["POST"])
def tds_cert():
    ar.mark_tds_certificate(int(request.form["receipt_id"]),
                            request.form.get("cert_no", ""),
                            request.form.get("cert_date", ""))
    audit.log(_user(), "tds_certificate", "receipt", request.form["receipt_id"])
    flash("TDS certificate recorded.")
    return redirect(url_for("ar.tds"))


@ar_bp.route("/gst")
def gst():
    if not _guard("gst"):
        return redirect(url_for("accounts.dashboard"))
    try:
        summary = ar.gst_summary()
        monthly = ar.gst_month_wise()
        by_client = ar.gst_client_wise()
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        summary, monthly, by_client = {}, [], []
    return render_template("accounts/gst.html", summary=summary, monthly=monthly,
                           by_client=by_client, user=_user())


@ar_bp.route("/profitability", methods=["GET", "POST"])
def profitability():
    if not auth.can_profit(_user()) and not auth.is_admin(_user()):
        flash("Profit reports are restricted to Admin and Management.")
        return redirect(url_for("accounts.dashboard"))
    seg_id = auth.user_segment_id(_user())
    if request.method == "POST" and request.form.get("action") != "export":
        flash("Use Expenses module to record costs. Profitability is computed automatically.")
        return redirect(url_for("ar.profitability"))
    try:
        import segment_service as seg
        rows = seg.segment_profitability(seg_id)
        segments = seg.list_segments()
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        rows, segments = [], []
    return render_template("accounts/profitability.html", segments=rows,
                           segment_list=segments, user=_user())


@ar_bp.route("/executive")
def executive():
    if not _guard("executive") and not auth.can(_user(), "dashboard"):
        return redirect(url_for("index"))
    seg_id = auth.user_segment_id(_user())
    try:
        summary = ar.executive_summary()
        charts = ar.executive_charts()
        import segment_service as seg
        seg_cards = seg.executive_segment_cards()
        if seg_id:
            seg_cards["segments"] = [s for s in seg_cards.get("segments", [])
                                     if s["BusinessSegmentId"] == seg_id]
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        summary, charts, seg_cards = {}, {}, {}
    return render_template("accounts/executive.html", summary=summary,
                           charts=charts, seg_cards=seg_cards, user=_user())


@ar_bp.route("/audit")
def audit_view():
    if not auth.is_admin(_user()):
        return redirect(url_for("accounts.dashboard"))
    try:
        rows = ar.audit_log()
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        rows = []
    return render_template("accounts/audit.html", rows=rows, user=_user())
