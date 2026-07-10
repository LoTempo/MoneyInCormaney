from datetime import date

from flask import g

from app.db import get_db
from app.utils import format_money


def month_bounds(day=None):
    current = day or date.today()
    month_start = current.replace(day=1)
    next_month = (
        date(month_start.year + 1, 1, 1)
        if month_start.month == 12
        else date(month_start.year, month_start.month + 1, 1)
    )
    return month_start, next_month


def scope_is_available(scope):
    return scope == "personal" or (scope == "family" and g.family is not None)


def access_condition(scope, alias="t"):
    personal_sql = f"({alias}.scope = 'personal' AND {alias}.user_id = %s)"
    personal_params = [g.user["id"]]

    if scope == "personal" or g.family is None:
        return personal_sql, personal_params

    family_sql = f"({alias}.scope = 'family' AND {alias}.family_id = %s)"
    family_params = [g.family["id"]]

    if scope == "family":
        return family_sql, family_params
    if scope in {"all", "compare"}:
        return f"({personal_sql} OR {family_sql})", personal_params + family_params
    raise ValueError("Unknown budget scope.")


def get_monthly_limit(scope, month_start):
    if scope == "personal":
        row = get_db().execute(
            """
            SELECT spending_limit
            FROM monthly_budgets
            WHERE scope = 'personal' AND user_id = %s AND month = %s
            """,
            (g.user["id"], month_start),
        ).fetchone()
    elif scope == "family" and g.family is not None:
        row = get_db().execute(
            """
            SELECT spending_limit
            FROM monthly_budgets
            WHERE scope = 'family' AND family_id = %s AND month = %s
            """,
            (g.family["id"], month_start),
        ).fetchone()
    else:
        return None

    return row["spending_limit"] if row else None


def save_monthly_limit(scope, month_start, amount):
    database = get_db()

    if scope == "personal":
        existing = database.execute(
            """
            SELECT id FROM monthly_budgets
            WHERE scope = 'personal' AND user_id = %s AND month = %s
            """,
            (g.user["id"], month_start),
        ).fetchone()
        if existing:
            database.execute(
                """
                UPDATE monthly_budgets
                SET spending_limit = %s, updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (amount, g.user["id"], existing["id"]),
            )
        else:
            database.execute(
                """
                INSERT INTO monthly_budgets
                    (scope, user_id, family_id, month, spending_limit, updated_by)
                VALUES ('personal', %s, NULL, %s, %s, %s)
                """,
                (g.user["id"], month_start, amount, g.user["id"]),
            )
    elif scope == "family" and g.family is not None:
        existing = database.execute(
            """
            SELECT id FROM monthly_budgets
            WHERE scope = 'family' AND family_id = %s AND month = %s
            """,
            (g.family["id"], month_start),
        ).fetchone()
        if existing:
            database.execute(
                """
                UPDATE monthly_budgets
                SET spending_limit = %s, updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (amount, g.user["id"], existing["id"]),
            )
        else:
            database.execute(
                """
                INSERT INTO monthly_budgets
                    (scope, user_id, family_id, month, spending_limit, updated_by)
                VALUES ('family', NULL, %s, %s, %s, %s)
                """,
                (g.family["id"], month_start, amount, g.user["id"]),
            )
    else:
        raise ValueError("Budget scope is unavailable.")

    database.commit()


def get_budget_summary(scope, day=None):
    if not scope_is_available(scope):
        return None

    month_start, next_month = month_bounds(day)
    condition, parameters = access_condition(scope)
    database = get_db()

    totals = database.execute(
        f"""
        SELECT
            COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS income,
            COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS budget_expenses,
            COALESCE(SUM(amount) FILTER (
                WHERE type IN ('expense', 'savings_withdrawal')
            ), 0) AS expenses,
            COALESCE(SUM(amount) FILTER (WHERE type = 'savings_deposit'), 0)
                AS savings_deposits,
            COALESCE(SUM(amount) FILTER (WHERE type = 'savings_withdrawal'), 0)
                AS savings_withdrawals
        FROM transactions AS t
        WHERE {condition}
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        """,
        parameters + [month_start, next_month],
    ).fetchone()

    savings_row = database.execute(
        f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN type = 'savings_deposit' THEN amount
                WHEN type = 'savings_withdrawal' THEN -amount
                ELSE 0
            END
        ), 0) AS savings
        FROM transactions AS t
        WHERE {condition}
        """,
        parameters,
    ).fetchone()

    spending_limit = get_monthly_limit(scope, month_start)
    balance = (
        spending_limit - totals["budget_expenses"]
        if spending_limit is not None
        else None
    )
    currency = g.user["currency"]

    return {
        "scope": scope,
        "month_start": month_start,
        "limit_set": spending_limit is not None,
        "limit_raw": spending_limit,
        "balance_raw": balance,
        "income_raw": totals["income"],
        "expenses_raw": totals["expenses"],
        "savings_raw": savings_row["savings"],
        "limit": format_money(spending_limit, currency) if spending_limit is not None else "Не задан",
        "balance": format_money(balance, currency) if balance is not None else "Не задан",
        "income": format_money(totals["income"], currency),
        "expenses": format_money(totals["expenses"], currency),
        "savings": format_money(savings_row["savings"], currency),
        "balance_negative": balance is not None and balance < 0,
    }
