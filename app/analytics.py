from datetime import date
from decimal import Decimal

from flask import Blueprint, g, render_template, request

from app.auth import login_required
from app.budget import access_condition, savings_access_condition
from app.db import get_db
from app.utils import format_money


analytics_bp = Blueprint("analytics", __name__)

MONTH_NAMES = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def next_month(month_start, offset=1):
    month_index = month_start.year * 12 + month_start.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def selected_month():
    raw_value = request.args.get("month", "")
    try:
        value = date.fromisoformat(f"{raw_value}-01")
        if 2000 <= value.year <= 2100:
            return value
    except ValueError:
        pass
    today = date.today()
    return date(today.year, today.month, 1)


def selected_year():
    try:
        year = int(request.args.get("year", date.today().year))
    except (TypeError, ValueError):
        year = date.today().year
    return min(2100, max(2000, year))


def selected_scope():
    scope = request.args.get("scope", "personal")
    if scope == "family" and g.family is not None:
        return "family"
    return "personal"


def operation_totals(scope, start, end):
    condition, parameters = access_condition(scope)
    row = get_db().execute(
        f"""
        SELECT COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'income'), 0) AS income,
               COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'expense'), 0) AS expenses
        FROM transactions AS t
        WHERE {condition}
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        """,
        parameters + [start, end],
    ).fetchone()
    return {"income": row["income"], "expenses": row["expenses"]}


def category_breakdown(scope, start, end):
    condition, parameters = access_condition(scope)
    rows = get_db().execute(
        f"""
        SELECT c.id, c.name, c.color, t.type, SUM(t.amount) AS amount
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        WHERE {condition}
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        GROUP BY c.id, c.name, c.color, t.type
        ORDER BY t.type, amount DESC, c.name
        """,
        parameters + [start, end],
    ).fetchall()

    currency = g.user["currency"]
    result = {"income": [], "expense": []}
    for row in rows:
        row["amount_display"] = format_money(row["amount"], currency)
        result[row["type"]].append(row)

    for category_type, items in result.items():
        largest = max((item["amount"] for item in items), default=Decimal("1"))
        for item in items:
            item["percent"] = float(item["amount"] / largest * 100)
    return result


def operation_months(scope, start, end):
    condition, parameters = access_condition(scope)
    result_rows = get_db().execute(
        f"""
        SELECT DATE_TRUNC('month', t.transaction_date)::date AS month,
               COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'income'), 0) AS income,
               COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'expense'), 0) AS expenses
        FROM transactions AS t
        WHERE {condition}
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        GROUP BY DATE_TRUNC('month', t.transaction_date)
        ORDER BY month
        """,
        parameters + [start, end],
    ).fetchall()
    by_month = {row["month"]: row for row in result_rows}
    currency = g.user["currency"]
    rows = []
    cursor = start
    while cursor < end:
        values = by_month.get(cursor, {})
        income = values.get("income", Decimal("0"))
        expenses = values.get("expenses", Decimal("0"))
        rows.append(
            {
                "date": cursor,
                "value": cursor.strftime("%Y-%m"),
                "label": MONTH_NAMES[cursor.month - 1],
                "income": income,
                "expenses": expenses,
                "income_display": format_money(income, currency),
                "expenses_display": format_money(expenses, currency),
            }
        )
        cursor = next_month(cursor)

    largest = max(
        [row[value] for row in rows for value in ("income", "expenses")]
        + [Decimal("1")]
    )
    for row in rows:
        row["income_percent"] = float(row["income"] / largest * 100)
        row["expenses_percent"] = float(row["expenses"] / largest * 100)
    return rows


def operation_report(scope, period, month_start, year):
    if period == "year":
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
        title = f"{year} год"
        months = operation_months(scope, start, end)
    else:
        start = month_start
        end = next_month(start)
        title = f"{MONTH_NAMES[start.month - 1]} {start.year}"
        months = []

    totals = operation_totals(scope, start, end)
    currency = g.user["currency"]
    totals["income_display"] = format_money(totals["income"], currency)
    totals["expenses_display"] = format_money(totals["expenses"], currency)
    totals["difference"] = totals["income"] - totals["expenses"]
    totals["difference_display"] = format_money(totals["difference"], currency)

    return {
        "title": title,
        "totals": totals,
        "categories": category_breakdown(scope, start, end),
        "months": months,
    }


def savings_report(scope, year):
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    condition, base_parameters = savings_access_condition(scope)
    database = get_db()

    opening_row = database.execute(
        f"""
        SELECT COALESCE(SUM(CASE
                   WHEN s.entry_type = 'deposit' THEN s.amount
                   ELSE -s.amount
               END), 0) AS balance
        FROM savings_entries AS s
        WHERE {condition} AND s.entry_date < %s
        """,
        base_parameters + [start],
    ).fetchone()

    result_rows = database.execute(
        f"""
        SELECT DATE_TRUNC('month', s.entry_date)::date AS month,
               COALESCE(SUM(s.amount) FILTER (WHERE s.entry_type = 'deposit'), 0) AS deposits,
               COALESCE(SUM(s.amount) FILTER (WHERE s.entry_type = 'withdrawal'), 0) AS withdrawals
        FROM savings_entries AS s
        WHERE {condition} AND s.entry_date >= %s AND s.entry_date < %s
        GROUP BY DATE_TRUNC('month', s.entry_date)
        ORDER BY month
        """,
        base_parameters + [start, end],
    ).fetchall()
    by_month = {row["month"]: row for row in result_rows}

    currency = g.user["currency"]
    balance = opening_row["balance"]
    rows = []
    cursor = start
    while cursor < end:
        values = by_month.get(cursor, {})
        deposits = values.get("deposits", Decimal("0"))
        withdrawals = values.get("withdrawals", Decimal("0"))
        change = deposits - withdrawals
        balance += change
        rows.append(
            {
                "label": MONTH_NAMES[cursor.month - 1],
                "deposits": deposits,
                "withdrawals": withdrawals,
                "change": change,
                "balance": balance,
                "deposits_display": format_money(deposits, currency),
                "withdrawals_display": format_money(withdrawals, currency),
                "change_display": format_money(change, currency),
                "balance_display": format_money(balance, currency),
            }
        )
        cursor = next_month(cursor)

    max_balance = max([row["balance"] for row in rows] + [Decimal("1")])
    for row in rows:
        row["balance_percent"] = float(max(row["balance"], 0) / max_balance * 100)

    entries = database.execute(
        f"""
        SELECT s.entry_type, s.amount, s.entry_date, s.reason, u.name AS member
        FROM savings_entries AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE {condition} AND s.entry_date >= %s AND s.entry_date < %s
        ORDER BY s.entry_date DESC, s.created_at DESC
        """,
        base_parameters + [start, end],
    ).fetchall()
    for entry in entries:
        entry["type_label"] = (
            "Пополнение" if entry["entry_type"] == "deposit" else "Трата"
        )
        entry["amount_display"] = format_money(
            entry["amount"], currency, entry["entry_type"]
        )

    deposits_total = sum((row["deposits"] for row in rows), Decimal("0"))
    withdrawals_total = sum((row["withdrawals"] for row in rows), Decimal("0"))
    return {
        "opening_display": format_money(opening_row["balance"], currency),
        "deposits_display": format_money(deposits_total, currency),
        "withdrawals_display": format_money(withdrawals_total, currency),
        "closing_display": format_money(balance, currency),
        "rows": rows,
        "entries": entries,
    }


@analytics_bp.get("/analytics")
@login_required
def index():
    scope = selected_scope()
    view = request.args.get("view", "operations")
    if view not in {"operations", "savings"}:
        view = "operations"

    period = request.args.get("period", "month")
    if period not in {"month", "year"}:
        period = "month"

    month_start = selected_month()
    year = selected_year() if request.args.get("year") else month_start.year
    report = (
        savings_report(scope, year)
        if view == "savings"
        else operation_report(scope, period, month_start, year)
    )

    return render_template(
        "analytics/index.html",
        scope=scope,
        view=view,
        period=period,
        month=month_start,
        month_value=month_start.strftime("%Y-%m"),
        previous_month=next_month(month_start, -1).strftime("%Y-%m"),
        following_month=next_month(month_start).strftime("%Y-%m"),
        year=year,
        report=report,
    )
