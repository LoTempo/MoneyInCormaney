from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.auth import login_required
from app.budget import (
    access_condition,
    get_budget_summary,
    month_bounds,
    save_monthly_limit,
    scope_is_available,
)
from app.db import get_db
from app.utils import (
    format_money,
    parse_nonnegative_amount,
    transaction_type_label,
)


dashboard_bp = Blueprint("dashboard", __name__)


def recent_transactions(scope="all", limit=8):
    condition, parameters = access_condition(scope)
    transactions = get_db().execute(
        f"""
        SELECT t.id, t.description, t.transaction_date AS date, t.amount,
               t.type, t.scope, t.user_id, c.name AS category,
               u.name AS member, (t.user_id = %s) AS can_edit
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        JOIN users AS u ON u.id = t.user_id
        WHERE {condition}
        ORDER BY t.transaction_date DESC, t.created_at DESC
        LIMIT %s
        """,
        [g.user["id"]] + parameters + [limit],
    ).fetchall()

    for transaction in transactions:
        transaction["amount"] = format_money(
            transaction["amount"],
            g.user["currency"],
            transaction["type"],
        )
        transaction["type_label"] = transaction_type_label(transaction["type"])
    return transactions


@dashboard_bp.get("/")
@login_required
def index():
    personal = get_budget_summary("personal")
    family = get_budget_summary("family") if g.family else None
    return render_template(
        "dashboard/index.html",
        personal=personal,
        family=family,
        recent_transactions=recent_transactions(),
    )


def render_budget_page(scope):
    if not scope_is_available(scope):
        flash("Сначала создайте семью или присоединитесь к ней.", "info")
        return redirect(url_for("family.family_view"))

    return render_template(
        "dashboard/scope.html",
        scope=scope,
        summary=get_budget_summary(scope),
        transactions=recent_transactions(scope, limit=20),
    )


@dashboard_bp.get("/budget/personal")
@login_required
def personal_budget():
    return render_budget_page("personal")


@dashboard_bp.get("/budget/family")
@login_required
def family_budget():
    return render_budget_page("family")


@dashboard_bp.post("/budget/<scope>/limit")
@login_required
def update_limit(scope):
    if scope not in {"personal", "family"} or not scope_is_available(scope):
        abort(404)
    if scope == "family" and g.family["role"] != "owner":
        abort(403)

    amount = parse_nonnegative_amount(request.form.get("spending_limit"))
    if amount is None:
        flash("Лимит должен быть неотрицательным числом.", "danger")
    else:
        month_start, _ = month_bounds()
        save_monthly_limit(scope, month_start, amount)
        flash(
            "Личный лимит обновлён." if scope == "personal" else "Семейный лимит обновлён.",
            "success",
        )

    return_to = request.form.get("return_to", "")
    allowed_targets = {
        "home": url_for("dashboard.index"),
        "personal": url_for("dashboard.personal_budget"),
        "family": url_for("dashboard.family_budget"),
    }
    return redirect(allowed_targets.get(return_to, url_for("dashboard.index")))
