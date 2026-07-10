from datetime import date

from flask import Blueprint, g, render_template

from app.auth import family_required
from app.db import get_db
from app.utils import format_money


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@family_required
def index():
    today = date.today()
    month_start = today.replace(day=1)
    next_month = (
        date(today.year + 1, 1, 1)
        if today.month == 12
        else date(today.year, today.month + 1, 1)
    )
    database = get_db()

    totals = database.execute(
        """
        SELECT
            COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS income,
            COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS expenses
        FROM transactions
        WHERE family_id = %s
          AND transaction_date >= %s
          AND transaction_date < %s
        """,
        (g.family["id"], month_start, next_month),
    ).fetchone()

    recent_transactions = database.execute(
        """
        SELECT t.description, t.transaction_date AS date, t.amount, t.type,
               c.name AS category
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        WHERE t.family_id = %s
        ORDER BY t.transaction_date DESC, t.created_at DESC
        LIMIT 5
        """,
        (g.family["id"],),
    ).fetchall()

    for transaction in recent_transactions:
        transaction["amount"] = format_money(
            transaction["amount"],
            g.user["currency"],
            transaction["type"],
        )

    income = totals["income"]
    expenses = totals["expenses"]
    savings = income - expenses

    return render_template(
        "dashboard/index.html",
        balance=format_money(savings, g.user["currency"]),
        income=format_money(income, g.user["currency"]),
        expenses=format_money(expenses, g.user["currency"]),
        savings=format_money(savings, g.user["currency"]),
        current_month=month_start.strftime("%m.%Y"),
        recent_transactions=recent_transactions,
    )
