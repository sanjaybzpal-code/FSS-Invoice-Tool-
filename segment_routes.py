"""Business segments, expenses, MIS, and management reporting routes."""

from __future__ import annotations

import os
from datetime import date

from flask import (Blueprint, flash, redirect, render_template, request,
                   send_file, url_for)

import audit
import auth
import expense_service as exp_svc
import ledger_service as ls
import report_exports as exports
import segment_service as seg_svc

segment_bp = Blueprint("segment", __name__, url_prefix="/accounts")

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(HERE, "Exports")


def _user():
    return auth.current_user()


def _seg_filter() -> int | None:
    return auth.user_segment_id(_user())


@segment_bp.before_request
@auth.login_required
def _login():
    pass


@segment_bp.route("/segments")
def segments_dashboard():
    if not auth.can(_user(), "segments_view") and not auth.is_admin(_user()):
        flash("You do not have permission for this section.")
        return redirect(url_for("index"))
    seg_id = _seg_filter()
    try:
        rows = seg_svc.segment_dashboard(seg_id)
        profitability = seg_svc.segment_profitability(seg_id)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        rows, profitability = [], []
    return render_template(
        "accounts/segments.html",
        segments=rows,
        profitability=profitability,
        user=_user(),
    )


@segment_bp.route("/management")
def management_dashboard():
    if not auth.can_management_dashboard(_user()):
        flash("Management dashboard is for Admin only.")
        return redirect(url_for("accounts.dashboard"))
    try:
        import ar_service as ar
        exec_sum = ar.executive_summary()
        seg_pl = seg_svc.segment_profitability()
        trend = seg_svc.segment_monthly_trend(12)
        today = date.today()
        month_exp = exp_svc.month_expense_total(today.year, today.month)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        exec_sum, seg_pl, trend, month_exp = {}, [], [], 0
    return render_template(
        "accounts/management.html",
        summary=exec_sum,
        segment_pl=seg_pl,
        trend=trend,
        month_expense=month_exp,
        user=_user(),
    )


@segment_bp.route("/expenses", methods=["GET", "POST"])
def expenses():
    if not auth.can_expenses(_user()):
        flash("Expense module is restricted to Admin.")
        return redirect(url_for("accounts.dashboard"))
    if request.method == "POST":
        action = request.form.get("action", "save")
        try:
            if action == "delete":
                eid = int(request.form["expense_id"])
                exp_svc.delete_expense(eid)
                audit.log(_user(), "delete_expense", "expense", str(eid))
                flash("Expense deleted.")
            elif action == "add_category":
                exp_svc.add_category(request.form.get("category_name", ""))
                audit.log(_user(), "add_expense_category", details=request.form.get("category_name"))
                flash("Category added.")
            else:
                manual = {}
                for k, v in request.form.items():
                    if k.startswith("alloc_pct_") and v:
                        manual[int(k.replace("alloc_pct_", ""))] = float(v)
                data = {
                    "expense_id": request.form.get("expense_id"),
                    "expense_date": request.form.get("expense_date"),
                    "category_id": request.form["category_id"],
                    "description": request.form.get("description"),
                    "amount": request.form.get("amount"),
                    "gst_amount": request.form.get("gst_amount"),
                    "vendor": request.form.get("vendor"),
                    "payment_mode": request.form.get("payment_mode"),
                    "reference": request.form.get("reference"),
                    "remarks": request.form.get("remarks"),
                    "allocation_type": request.form.get("allocation_type", "segment"),
                    "segment_id": request.form.get("segment_id"),
                    "manual_alloc": manual,
                }
                eid = exp_svc.save_expense(data, _user())
                audit.log(_user(), "save_expense", "expense", str(eid))
                flash("Expense saved.")
            return redirect(url_for("segment.expenses"))
        except Exception as exc:  # noqa: BLE001
            flash(str(exc))
    try:
        rows = exp_svc.list_expenses()
        categories = exp_svc.list_categories()
        segments = seg_svc.list_segments()
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        rows, categories, segments = [], [], []
    edit_id = request.args.get("edit", type=int)
    edit_exp = exp_svc.get_expense(edit_id) if edit_id else None
    return render_template(
        "accounts/expenses.html",
        expenses=rows,
        categories=categories,
        segments=segments,
        edit_expense=edit_exp,
        today=date.today().strftime("%d-%m-%Y"),
        user=_user(),
    )


@segment_bp.route("/mis")
def mis_report():
    if not auth.can_profit(_user()) and not auth.is_admin(_user()):
        flash("MIS reports are restricted.")
        return redirect(url_for("accounts.dashboard"))
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    seg_id = _seg_filter()
    try:
        mis = seg_svc.mis_report(year, month, seg_id)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
        mis = {"year": year, "month": month, "profitability": [], "top_clients": [],
               "top_expenses": [], "segments": []}
    return render_template("accounts/mis.html", mis=mis, user=_user())


@segment_bp.route("/export/<report>/<fmt>")
def export_report(report, fmt):
    user = _user()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    seg_id = _seg_filter()
    try:
        if report == "profitability":
            if not auth.can_profit(user) and not auth.is_admin(user):
                flash("Not allowed.")
                return redirect(url_for("accounts.dashboard"))
            rows = seg_svc.segment_profitability(seg_id)
            path = os.path.join(EXPORT_DIR, f"Segment_PL.{fmt}")
            if fmt == "xlsx":
                exports.export_segment_pl_excel(path, rows)
            else:
                exports.export_segment_pl_pdf(path, rows)
        elif report == "expenses":
            if not auth.can_expenses(user):
                flash("Not allowed.")
                return redirect(url_for("accounts.dashboard"))
            rows = exp_svc.list_expenses()
            path = os.path.join(EXPORT_DIR, "Expense_Register.xlsx")
            exports.export_expenses_excel(path, rows)
        elif report == "mis":
            if not auth.can_profit(user) and not auth.is_admin(user):
                flash("Not allowed.")
                return redirect(url_for("accounts.dashboard"))
            y = request.args.get("year", type=int) or date.today().year
            m = request.args.get("month", type=int) or date.today().month
            mis = seg_svc.mis_report(y, m, seg_id)
            path = os.path.join(EXPORT_DIR, f"MIS_{y}_{m:02d}.xlsx")
            exports.export_mis_excel(path, mis)
        else:
            flash("Unknown report.")
            return redirect(url_for("accounts.dashboard"))
        audit.log(user, "export", report, fmt)
        return send_file(path, as_attachment=True)
    except Exception as exc:  # noqa: BLE001
        flash(str(exc))
    return redirect(url_for("accounts.dashboard"))
