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
    if scope == "personal":
        return bool(g.user and g.user["personal_budget_enabled"])
    if scope == "family":
        return bool(
            g.user
            and g.user["family_budget_enabled"]
            and g.family is not None
        )
    return False


def enabled_scopes():
    scopes = []
    if scope_is_available("personal"):
        scopes.append("personal")
    if scope_is_available("family"):
        scopes.append("family")
    return scopes


def access_condition(scope, alias="t"):
    personal_sql = f"({alias}.scope = 'personal' AND {alias}.user_id = %s)"
    personal_params = [g.user["id"]]
    personal_enabled = scope_is_available("personal")
    family_enabled = scope_is_available("family")

    if scope == "personal":
        return (personal_sql, personal_params) if personal_enabled else ("FALSE", [])
    if scope == "family":
        if not family_enabled:
            return "FALSE", []
        return (
            f"({alias}.scope = 'family' AND {alias}.family_id = %s)",
            [g.family["id"]],
        )
    if scope in {"all", "compare"}:
        conditions = []
        parameters = []
        if personal_enabled:
            conditions.append(personal_sql)
            parameters.extend(personal_params)
        if family_enabled:
            conditions.append(
                f"({alias}.scope = 'family' AND {alias}.family_id = %s)"
            )
            parameters.append(g.family["id"])
        return (f"({' OR '.join(conditions)})", parameters) if conditions else ("FALSE", [])
    raise ValueError("Unknown budget scope.")


def savings_access_condition(scope, alias="s"):
    personal_sql = f"({alias}.scope = 'personal' AND {alias}.user_id = %s)"
    personal_params = [g.user["id"]]

    personal_enabled = scope_is_available("personal")
    family_enabled = scope_is_available("family")

    if scope == "personal":
        return (personal_sql, personal_params) if personal_enabled else ("FALSE", [])
    if scope == "family":
        if not family_enabled:
            return "FALSE", []
        return (
            f"({alias}.scope = 'family' AND {alias}.family_id = %s)",
            [g.family["id"]],
        )
    if scope in {"all", "compare"}:
        conditions = []
        parameters = []
        if personal_enabled:
            conditions.append(personal_sql)
            parameters.extend(personal_params)
        if family_enabled:
            conditions.append(
                f"({alias}.scope = 'family' AND {alias}.family_id = %s)"
            )
            parameters.append(g.family["id"])
        return (f"({' OR '.join(conditions)})", parameters) if conditions else ("FALSE", [])
    raise ValueError("Unknown savings scope.")


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
    savings_condition, savings_parameters = savings_access_condition(scope)
    if scope == "personal":
        limit_condition = "mb.scope = 'personal' AND mb.user_id = %s"
        limit_parameters = [g.user["id"], month_start]
    else:
        limit_condition = "mb.scope = 'family' AND mb.family_id = %s"
        limit_parameters = [g.family["id"], month_start]

    summary = get_db().execute(
        f"""
        WITH transaction_totals AS (
            SELECT COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'income'), 0) AS income,
                   COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'expense'), 0) AS expenses
            FROM transactions AS t
            WHERE {condition}
              AND t.transaction_date >= %s
              AND t.transaction_date < %s
        ),
        savings_total AS (
            SELECT COALESCE(SUM(CASE
                       WHEN s.entry_type = 'deposit' THEN s.amount
                       WHEN s.entry_type = 'withdrawal' THEN -s.amount
                       ELSE 0
                   END), 0) AS savings
            FROM savings_entries AS s
            WHERE {savings_condition}
        )
        SELECT totals.income, totals.expenses, savings.savings,
               (SELECT mb.spending_limit
                FROM monthly_budgets AS mb
                WHERE {limit_condition} AND mb.month = %s
                LIMIT 1) AS spending_limit
        FROM transaction_totals AS totals
        CROSS JOIN savings_total AS savings
        """,
        parameters
        + [month_start, next_month]
        + savings_parameters
        + limit_parameters,
    ).fetchone()

    spending_limit = summary["spending_limit"]
    balance = (
        spending_limit - summary["expenses"]
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
        "income_raw": summary["income"],
        "expenses_raw": summary["expenses"],
        "savings_raw": summary["savings"],
        "limit": format_money(spending_limit, currency) if spending_limit is not None else "Не задан",
        "balance": format_money(balance, currency) if balance is not None else "Не задан",
        "income": format_money(summary["income"], currency),
        "expenses": format_money(summary["expenses"], currency),
        "savings": format_money(summary["savings"], currency),
        "balance_negative": balance is not None and balance < 0,
    }


def get_savings_entries(scope, limit=20):
    if not scope_is_available(scope):
        return []

    condition, parameters = savings_access_condition(scope)
    entries = get_db().execute(
        f"""
        SELECT s.id, s.entry_type, s.amount, s.entry_date, s.reason,
               s.scope, s.user_id, u.name AS member
        FROM savings_entries AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE {condition}
        ORDER BY s.entry_date DESC, s.created_at DESC
        LIMIT %s
        """,
        parameters + [limit],
    ).fetchall()

    for entry in entries:
        entry["amount_display"] = format_money(
            entry["amount"],
            g.user["currency"],
            entry["entry_type"],
        )
        entry["type_label"] = (
            "Пополнение" if entry["entry_type"] == "deposit" else "Трата"
        )
    return entries
