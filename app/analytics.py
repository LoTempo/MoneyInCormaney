from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, flash, g, render_template, request

from app.auth import login_required
from app.budget import (
    access_condition,
    get_budget_summary,
    month_bounds,
    savings_access_condition,
)
from app.db import get_db
from app.utils import format_money


analytics_bp = Blueprint("analytics", __name__)


def period_bounds(period, date_from_raw="", date_to_raw=""):
    today = date.today()
    if period == "day":
        return today, today + timedelta(days=1)
    if period == "week":
        return today - timedelta(days=6), today + timedelta(days=1)
    if period == "month":
        return month_bounds(today)
    if period == "quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start = date(today.year, quarter_month, 1)
        end = (
            date(today.year + 1, 1, 1)
            if quarter_month == 10
            else date(today.year, quarter_month + 3, 1)
        )
        return start, end
    if period == "year":
        return date(today.year, 1, 1), date(today.year + 1, 1, 1)
    if period == "all":
        return None, today + timedelta(days=1)
    if period == "custom":
        try:
            start = date.fromisoformat(date_from_raw)
            inclusive_end = date.fromisoformat(date_to_raw)
        except ValueError:
            return None, None
        if start > inclusive_end or (inclusive_end - start).days > 3650:
            return None, None
        return start, inclusive_end + timedelta(days=1)
    return month_bounds(today)


def automatic_grouping(start, end):
    if start is None:
        return "year"
    days = (end - start).days
    if days <= 45:
        return "day"
    if days <= 180:
        return "week"
    if days <= 1095:
        return "month"
    return "year"


def period_label(period_date, grouping):
    if grouping == "day":
        return period_date.strftime("%d.%m.%Y")
    if grouping == "week":
        return f"Неделя с {period_date.strftime('%d.%m.%Y')}"
    if grouping == "month":
        return period_date.strftime("%m.%Y")
    return period_date.strftime("%Y")


def grouped_date_expression(alias, column, grouping):
    source = f"{alias}.{column}"
    return {
        "day": source,
        "week": f"DATE_TRUNC('week', {source})::date",
        "month": f"DATE_TRUNC('month', {source})::date",
        "year": f"DATE_TRUNC('year', {source})::date",
    }[grouping]


def add_date_conditions(alias, column, start, end, parameters):
    conditions = []
    if start is not None:
        conditions.append(f"{alias}.{column} >= %s")
        parameters.append(start)
    conditions.append(f"{alias}.{column} < %s")
    parameters.append(end)
    return " AND ".join(conditions)


def analytics_for_scope(scope, start, end, grouping):
    database = get_db()
    transaction_condition, transaction_parameters = access_condition(scope)
    transaction_group = grouped_date_expression("t", "transaction_date", grouping)
    transaction_dates = add_date_conditions(
        "t", "transaction_date", start, end, transaction_parameters
    )
    transaction_rows = database.execute(
        f"""
        SELECT {transaction_group} AS period,
               COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS income,
               COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS expenses
        FROM transactions AS t
        WHERE {transaction_condition} AND {transaction_dates}
        GROUP BY {transaction_group}
        """,
        transaction_parameters,
    ).fetchall()

    savings_condition, savings_parameters = savings_access_condition(scope)
    savings_group = grouped_date_expression("s", "entry_date", grouping)
    savings_dates = add_date_conditions(
        "s", "entry_date", start, end, savings_parameters
    )
    savings_rows = database.execute(
        f"""
        SELECT {savings_group} AS period,
               COALESCE(SUM(amount) FILTER (
                   WHERE entry_type = 'deposit'
               ), 0) AS savings_deposits,
               COALESCE(SUM(amount) FILTER (
                   WHERE entry_type = 'withdrawal'
               ), 0) AS savings_withdrawals
        FROM savings_entries AS s
        WHERE {savings_condition} AND {savings_dates}
        GROUP BY {savings_group}
        """,
        savings_parameters,
    ).fetchall()

    points = {}
    for row in transaction_rows:
        points[row["period"]] = {
            "period": row["period"],
            "income": row["income"],
            "expenses": row["expenses"],
            "savings_deposits": Decimal("0"),
            "savings_withdrawals": Decimal("0"),
        }
    for row in savings_rows:
        point = points.setdefault(
            row["period"],
            {
                "period": row["period"],
                "income": Decimal("0"),
                "expenses": Decimal("0"),
                "savings_deposits": Decimal("0"),
                "savings_withdrawals": Decimal("0"),
            },
        )
        point["savings_deposits"] = row["savings_deposits"]
        point["savings_withdrawals"] = row["savings_withdrawals"]

    rows = [points[key] for key in sorted(points)]
    raw_values = []
    currency = g.user["currency"]
    for row in rows:
        row["savings_change"] = row["savings_deposits"] - row["savings_withdrawals"]
        row["label"] = period_label(row["period"], grouping)
        raw_values.extend(
            [
                row["income"],
                row["expenses"],
                row["savings_deposits"],
                row["savings_withdrawals"],
            ]
        )
        for name in (
            "income",
            "expenses",
            "savings_deposits",
            "savings_withdrawals",
            "savings_change",
        ):
            row[f"{name}_display"] = format_money(row[name], currency)

    totals = {
        "income": sum((row["income"] for row in rows), Decimal("0")),
        "expenses": sum((row["expenses"] for row in rows), Decimal("0")),
        "savings_deposits": sum(
            (row["savings_deposits"] for row in rows), Decimal("0")
        ),
        "savings_withdrawals": sum(
            (row["savings_withdrawals"] for row in rows), Decimal("0")
        ),
    }
    totals["savings_change"] = totals["savings_deposits"] - totals["savings_withdrawals"]

    category_parameters = list(transaction_parameters)
    categories = database.execute(
        f"""
        SELECT c.name, SUM(t.amount) AS amount
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        WHERE {transaction_condition} AND {transaction_dates}
          AND t.type = 'expense'
        GROUP BY c.id, c.name
        ORDER BY amount DESC
        LIMIT 8
        """,
        category_parameters,
    ).fetchall()
    for category in categories:
        category["amount_display"] = format_money(category["amount"], currency)

    summary = get_budget_summary(scope)
    return {
        "scope": scope,
        "rows": rows,
        "categories": categories,
        "max_value": max(raw_values + [Decimal("1")]),
        "totals": {
            **totals,
            **{
                f"{name}_display": format_money(value, currency)
                for name, value in totals.items()
            },
        },
        "savings_state": summary["savings"],
        "balance": summary["balance"],
        "balance_negative": summary["balance_negative"],
    }


@analytics_bp.get("/analytics")
@login_required
def index():
    selected_scope = request.args.get("scope", "personal")
    if selected_scope not in {"personal", "family", "all"}:
        selected_scope = "personal"
    if selected_scope in {"family", "all"} and g.family is None:
        selected_scope = "personal"

    period = request.args.get("period", "month")
    if period not in {"day", "week", "month", "quarter", "year", "all", "custom"}:
        period = "month"
    date_from_raw = request.args.get("date_from", "")
    date_to_raw = request.args.get("date_to", "")
    start, end = period_bounds(period, date_from_raw, date_to_raw)
    if end is None:
        flash("Проверьте выбранные даты. Максимальный интервал — 10 лет.", "danger")
        period = "month"
        start, end = period_bounds(period)

    grouping = request.args.get("group_by", "auto")
    if grouping not in {"auto", "day", "week", "month", "year"}:
        grouping = "auto"
    effective_grouping = automatic_grouping(start, end) if grouping == "auto" else grouping
    scopes = (
        ["personal", "family"]
        if selected_scope == "all" and g.family is not None
        else [selected_scope]
    )
    series = [analytics_for_scope(scope, start, end, effective_grouping) for scope in scopes]

    return render_template(
        "analytics/index.html",
        series=series,
        selected_scope=selected_scope,
        selected_period=period,
        selected_grouping=grouping,
        effective_grouping=effective_grouping,
        date_from=date_from_raw or (start.isoformat() if start else ""),
        date_to=date_to_raw or ((end - timedelta(days=1)).isoformat()),
    )
